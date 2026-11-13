"""Pre-screen and A4 Pattern Classifier with RAG (task 4.4; FR-020, FR-030).

Pre-screen (code): a provisional deterministic score plus KB retrieval. Clear cases skip
the LLM classifier (docs/05 A0 rule 1).

Classifier (reasoning LLM): maps the evidence to typologies from the KB enumeration,
decides whether to interview, and may suggest a bounded score nudge (ADR-003). Output is
validated: unknown typology codes, unknown evidence IDs, and already-asked facts are
dropped. On any LLM problem, typologies come from retrieval alone.
"""

from __future__ import annotations

import json
from typing import Any, get_args

from pydantic import BaseModel, Field

from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState, case_text, dump, read
from scamsaathi.kb.retrieval import rank_typologies
from scamsaathi.prompts import load_prompt, untrusted_block
from scamsaathi.schemas import (
    ClassificationResult,
    InputMode,
    IntelResult,
    MissingFact,
    PrescreenResult,
    Signal,
    SignalName,
    TypologyMatch,
)
from scamsaathi.tools.risk_scorer import Situation, score

ASKABLE_FACTS: tuple[str, ...] = get_args(MissingFact)
# Retrieval-only fallback: typologies are reported for advice, but carry no confidence
# into the score, so degraded mode scores exactly like the rules-only baseline (B0).
RETRIEVAL_CONFIDENCE = 0.0
DEFAULT_FACTS: tuple[MissingFact, ...] = ("asked_to_pay", "asked_for_secret", "money_sent")


def _signals(state: ScamState) -> list[Signal]:
    return [Signal.model_validate(s) for s in state.get("signals", [])]


def _evidence_ids(state: ScamState) -> set[str]:
    intel = read(state, "intel", IntelResult) or IntelResult()
    kb = {f"K{i}" for i in range(1, len(state.get("kb_chunk_ids", [])) + 1)}
    return {s.evidence_id for s in _signals(state)} | {f.evidence_id for f in intel.findings} | kb


# --- Pre-screen ----------------------------------------------------------------------


def _confidence(level: str, situation: Situation, overrides: list[str], combos: int,
                signals: int, strong_intel: bool, mitigated: bool) -> tuple[float, str]:
    if situation.child_involved or situation.money_sent or situation.credentials_shared:
        return 0.95, "user reports harm already done or a child at risk"
    if level == "CRITICAL":
        return 0.92, "provisional score is critical"
    if level == "HIGH" and ("blocklist_floor" in overrides or combos):
        return 0.88, "high score backed by a blocklist hit or a signal combination"
    if level == "HIGH":
        return 0.75, "high score from separate signals"
    if level == "LOW" and mitigated and not signals and not strong_intel:
        return 0.9, "only evidence of legitimacy (official domain or known number)"
    if level == "MEDIUM":
        return 0.6, "moderate evidence"
    return (0.5, "weak evidence") if signals or strong_intel else (0.35, "no clear signals")


def prescreen(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    signals = _signals(state)
    intel = read(state, "intel", IntelResult) or IntelResult()
    situation = read(state, "situation", Situation) or Situation()
    provisional = score(signals, intel, ctx.scoring, situation=situation)

    results = ctx.retriever.retrieve(case_text(state), k=ctx.top_k)
    candidates = [{"code": code, "score": s} for code, s in rank_typologies(results)[:3]]

    combos = sum(1 for c in provisional.contributions if c.factor.startswith("combo:"))
    mitigated = any(c.factor.startswith("mitigation:") for c in provisional.contributions)
    strong_intel = any(f.severity in ("medium", "high") for f in intel.findings)
    # A link on its own is not a warning sign when intel has verified where it goes.
    warning_signals = [s for s in signals if s.name is not SignalName.LINK_PRESENT]
    confidence, reason = _confidence(provisional.level, situation, provisional.overrides,
                                     combos, len(warning_signals), strong_intel, mitigated)
    verified_genuine = (provisional.level == "LOW" and mitigated and not warning_signals
                        and not strong_intel)
    skip = confidence >= ctx.routing.prescreen_high_confidence and (
        verified_genuine or situation.child_involved
    )
    result = PrescreenResult(confidence=confidence, provisional_level=provisional.level,
                             provisional_value=provisional.value, reason=reason,
                             skip_classifier=skip)
    return {
        "prescreen": dump(result),
        "candidates": candidates,
        "kb_chunk_ids": [r.chunk.chunk_id for r in results],
    }


def retrieval_classification(state: ScamState, needs_more_info: bool = False,
                             missing: list[str] | None = None) -> ClassificationResult:
    """Typologies from retrieval only; reported only when the case is at least MEDIUM."""
    pre = read(state, "prescreen", PrescreenResult)
    matches: list[TypologyMatch] = []
    if pre is not None and pre.provisional_level != "LOW":
        matches = [TypologyMatch(code=c["code"], confidence=RETRIEVAL_CONFIDENCE)
                   for c in state.get("candidates", [])[:2]]
    return ClassificationResult(matches=matches, needs_more_info=needs_more_info,
                                missing_facts=missing or [],
                                kb_chunk_ids=state.get("kb_chunk_ids", []))


# --- Classifier (LLM) -----------------------------------------------------------------


class MatchOut(BaseModel):
    code: str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)


class ClassifierOutput(BaseModel):
    matches: list[MatchOut] = Field(default_factory=list, max_length=3)
    needs_more_info: bool = False
    missing_facts: list[MissingFact] = Field(default_factory=list, max_length=3)
    score_adjustment: int = Field(default=0, ge=-10, le=10)
    adjustment_reason: str | None = Field(default=None, max_length=200)


def _context_block(state: ScamState, ctx: AgentContext) -> str:
    intel = read(state, "intel", IntelResult) or IntelResult()
    signals = [{"id": s.evidence_id, "name": s.name.value, "text": s.evidence_span}
               for s in _signals(state)]
    findings = [{"id": f.evidence_id, "check": f.check, "severity": f.severity, "detail": f.detail}
                for f in intel.findings]
    chunks = {c.chunk_id: c for c in ctx.kb.chunks}
    knowledge = [
        {"id": f"K{i}", "typology": chunks[cid].code, "text": chunks[cid].text[:600]}
        for i, cid in enumerate(state.get("kb_chunk_ids", []), start=1) if cid in chunks
    ]
    typologies = {code: t.name for code, t in sorted(ctx.kb.typologies.items())}
    askable = [f for f in ASKABLE_FACTS if f not in state.get("asked_facts", [])]
    return "\n".join([
        "SIGNALS: " + json.dumps(signals, ensure_ascii=False),
        "INTEL: " + json.dumps(findings, ensure_ascii=False),
        "KNOWLEDGE: " + json.dumps(knowledge, ensure_ascii=False),
        "TYPOLOGIES: " + json.dumps(typologies, ensure_ascii=False),
        "ASKABLE_FACTS: " + json.dumps(askable),
        f"INPUT_MODE: {state.get('input_mode', InputMode.MESSAGE.value)}",
    ])


def interview_useful(state: ScamState) -> bool:
    """Questions about "what did they ask you" fit a described interaction, not a quiet notice.

    A pasted message with no warning signs (no signals, no medium or high intel finding),
    such as a bank's OTP notice, is assessed as it is. Situation descriptions, number or
    link queries, and messages with any warning sign may still lead to questions.
    """
    if state.get("input_mode") != InputMode.MESSAGE.value:
        return True
    intel = read(state, "intel", IntelResult) or IntelResult()
    return bool(state.get("signals")) or any(
        f.severity in ("medium", "high") for f in intel.findings
    )


def validate(output: ClassifierOutput, state: ScamState, ctx: AgentContext) -> ClassificationResult:
    known = _evidence_ids(state)
    asked = set(state.get("asked_facts", []))
    matches: list[TypologyMatch] = []
    for m in output.matches:
        if m.code not in ctx.kb.typologies or any(x.code == m.code for x in matches):
            continue
        ids = [i for i in m.evidence_ids if i in known]
        matches.append(TypologyMatch(code=m.code, confidence=m.confidence,
                                     supporting_evidence_ids=ids))
    missing: list[str] = [str(f) for f in dict.fromkeys(output.missing_facts) if f not in asked]
    return ClassificationResult(
        matches=matches,
        needs_more_info=output.needs_more_info and bool(missing) and interview_useful(state),
        missing_facts=missing,
        kb_chunk_ids=state.get("kb_chunk_ids", []),
    )


def classify(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    prompt = load_prompt("classify")
    user = _context_block(state, ctx) + "\n" + untrusted_block(case_text(state))
    result, update = ctx.call_llm(
        state, node="classify", prompt=prompt, tier="reasoning", user=user,
        schema=ClassifierOutput, reserve=ctx.routing.llm_reserve_for_explanation,
    )
    if result is not None:
        classification = validate(result.output, state, ctx)
        adjustment = None
        out = result.output
        if out.score_adjustment and out.adjustment_reason and len(out.adjustment_reason) >= 3:
            adjustment = {"points": out.score_adjustment, "reason": out.adjustment_reason}
        update.update({"classification": dump(classification), "classification_source": "llm",
                       "llm_adjustment": adjustment})
        return update

    # Fallback: retrieval typologies, and the static interview only for vague first-person
    # accounts with no clear signals (a pasted message is assessed as it is).
    vague = (state.get("input_mode") == InputMode.SITUATION.value and not state.get("signals")
             and state.get("followups_asked", 0) == 0)
    asked = state.get("asked_facts", [])
    missing: list[str] = [str(f) for f in DEFAULT_FACTS if f not in asked] if vague else []
    classification = retrieval_classification(state, needs_more_info=bool(missing), missing=missing)
    update.update({"classification": dump(classification), "classification_source": "retrieval",
                   "llm_adjustment": None})
    return update
