"""A2 Signal Extraction agent (task 4.2; FR-010 to FR-013).

Hybrid: the rule-based detector always runs; the fast LLM adds signals the rules miss.
Every LLM signal must quote an evidence span that really appears in the masked text, or
it is dropped (docs/05 A2, hallucination mitigation). On any LLM problem the rule
signals are used alone.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from pydantic import BaseModel, Field

from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState, case_text, read
from scamsaathi.prompts import load_prompt, untrusted_block
from scamsaathi.schemas import IntelResult, Signal, SignalName
from scamsaathi.tools import rule_signals
from scamsaathi.tools.risk_scorer import Situation

# The LLM may not set link_present: links are detected deterministically from entities.
_LLM_SIGNALS: Final = frozenset(SignalName) - {SignalName.LINK_PRESENT}
MAX_LLM_CONFIDENCE: Final = 0.95
_SPACE: Final = re.compile(r"\s+")
# Intel checks that confirm a sender is who it says it is (scoring mitigations).
_VERIFIED_CHECKS: Final = frozenset({"official_domain", "allowlist"})
# Signals that make a verified sender suspicious again (possible spoofing or misuse).
_RISKY_REQUESTS: Final = frozenset({
    SignalName.CREDENTIAL_REQUEST, SignalName.PAYMENT_REQUEST, SignalName.APP_INSTALL_REQUEST,
    SignalName.THREAT, SignalName.SECRECY,
})


class ExtractedSignal(BaseModel):
    name: SignalName
    confidence: float = Field(ge=0, le=1)
    evidence_span: str = Field(min_length=2, max_length=160)


class ExtractionOutput(BaseModel):
    signals: list[ExtractedSignal] = Field(default_factory=list, max_length=15)
    impersonated_org: str | None = Field(default=None, max_length=60)


def _norm(text: str) -> str:
    return _SPACE.sub(" ", text).strip().lower()


def span_in_text(span: str, text: str) -> bool:
    """True when the span (ignoring case, whitespace, and edge quotes) occurs in the text."""
    needle = _norm(span).strip("\"'“”‘’ .,")
    return len(needle) >= 2 and needle in _norm(text)


def reconcile_with_intel(
    llm: list[ExtractedSignal], rule: list[Signal], intel: IntelResult
) -> list[ExtractedSignal]:
    """Drop an LLM "claims to be a bank or official" signal when intel verified the sender.

    A message that names HDFC Bank and links to HDFC's official domain is a claim, not an
    impersonation. The signal is kept whenever anything contradicts the verification: any
    medium or high finding (for example a name and link mismatch, an ordinary mobile
    number, or a blocklist hit) or any request for secrets, money, an app, secrecy, or a
    threat. Rule-based signals are never removed, so degraded runs still match B0.
    """
    verified = any(f.check in _VERIFIED_CHECKS for f in intel.findings)
    contradicted = any(f.severity in ("medium", "high") for f in intel.findings)
    names = {s.name for s in rule} | {s.name for s in llm}
    if not verified or contradicted or names & _RISKY_REQUESTS:
        return llm
    return [s for s in llm if s.name is not SignalName.AUTHORITY_IMPERSONATION]


def merge(rule: list[Signal], llm: list[ExtractedSignal], text: str) -> list[Signal]:
    """Strongest grounded evidence per signal name; IDs renumbered S1.. in enum order."""
    best: dict[SignalName, tuple[float, str]] = {s.name: (s.confidence, s.evidence_span) for s in rule}
    for item in llm:
        if item.name not in _LLM_SIGNALS or not span_in_text(item.evidence_span, text):
            continue
        confidence = min(item.confidence, MAX_LLM_CONFIDENCE)
        if item.name not in best or confidence > best[item.name][0]:
            best[item.name] = (confidence, item.evidence_span.strip()[:80])
    ordered = [name for name in SignalName if name in best]
    return [
        Signal(name=name, confidence=round(best[name][0], 2), evidence_span=best[name][1],
               evidence_id=f"S{i}")
        for i, name in enumerate(ordered, start=1)
    ]


def extraction(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    text = case_text(state)
    has_link = any(e["kind"] == "url" for e in state.get("entities", []))
    rule = rule_signals.detect(text, has_link=has_link)

    prompt = load_prompt("extract")
    user = (
        "RULE_SIGNALS_ALREADY_FOUND: "
        + json.dumps([s.name.value for s in rule])
        + "\nFind any further signals, and confirm or correct these.\n"
        + untrusted_block(text)
    )
    result, update = ctx.call_llm(
        state, node="extract", prompt=prompt, tier="fast", user=user, schema=ExtractionOutput,
        reserve=ctx.routing.llm_reserve_for_explanation,
    )
    llm_signals = result.output.signals if result else []
    intel = read(state, "intel", IntelResult) or IntelResult()
    signals = merge(rule, reconcile_with_intel(llm_signals, rule, intel), text)

    # Situation facts come from rules over the masked text and answers (deterministic),
    # with explicit confirmations or denials taking precedence.
    previous = read(state, "situation", Situation) or Situation()
    found = Situation(**rule_signals.detect_situation(text))

    creds_shared = found.credentials_shared
    if found.credentials_exposure.status == "unknown" and previous.credentials_shared:
        creds_shared = True

    app_inst = found.app_installed
    if found.app_installation.status == "unknown" and previous.app_installed:
        app_inst = True

    money_sent = found.money_sent or previous.money_sent
    link_clicked = found.link_clicked or previous.link_clicked
    child_involved = found.child_involved or previous.child_involved

    situation = Situation(
        money_sent=money_sent,
        credentials_shared=creds_shared,
        link_clicked=link_clicked,
        app_installed=app_inst,
        child_involved=child_involved,
        credentials_exposure=found.credentials_exposure if found.credentials_exposure.status != "unknown" else previous.credentials_exposure,
        app_installation=found.app_installation if found.app_installation.status != "unknown" else previous.app_installation,
        money_loss=found.money_loss if found.money_loss.status != "unknown" else previous.money_loss,
        unresolved_uncertainties=found.unresolved_uncertainties,
    )

    org = result.output.impersonated_org if result else None
    if org and not span_in_text(org, text):
        org = None  # same grounding rule as signals
    update.update({
        "signals": [s.model_dump(mode="json") for s in signals],
        "situation": situation.model_dump(),
        "impersonated_org": org,
    })
    return update
