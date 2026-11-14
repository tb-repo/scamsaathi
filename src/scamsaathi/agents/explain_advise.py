"""A7 Explanation and A8 Advisory, combined into one LLM call (task 4.5; FR-033, FR-035,
FR-050 to FR-054, FR-083).

1. Advice is chosen deterministically from curated templates and verified contacts.
2. One reasoning-tier call writes the headline, evidence-linked reasons, and an
   uncertainty note, and rewords the actions into the user's language.
3. Everything the LLM returns is validated. Reasons must cite known evidence IDs. The
   headline may not state a different risk level. Text may not name laws or make absolute
   claims. A reworded action may not add or change any number or link. Anything that fails
   falls back to the deterministic template for that field.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from pydantic import BaseModel, Field

from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState, case_text, dump, read
from scamsaathi.kb.advice import build_advice
from scamsaathi.prompts import load_prompt, untrusted_block
from scamsaathi.schemas import (
    Action,
    AdviceBundle,
    Explanation,
    IntelResult,
    Reason,
    RiskScore,
    Signal,
    SignalName,
)
from scamsaathi.tools import rule_signals
from scamsaathi.tools.risk_scorer import Situation

# --- Validation rules -----------------------------------------------------------------

_BANNED: Final = re.compile(
    r"100\s?% (?:safe|scam)|definitely (?:a )?(?:scam|safe|fraud)|completely safe|"
    r"guaranteed|no risk at all|certainly (?:a )?scam",
    re.I,
)
# FR-083: no legal sections, charges, or punishments in user-facing text.
_LEGAL: Final = re.compile(
    r"\b(?:section|sec\.|u/s|s\.\s?\d|bns|bnss|ipc|it act|pocso|imprisonment|jail|punishable)\b",
    re.I,
)
_LEVEL_MENTION: Final = re.compile(
    r"\b(very high|extremely high|critical|high|medium|moderate|low)[\s-]*risk\b", re.I
)
_LEVEL_OF: Final = {
    "very high": "CRITICAL", "extremely high": "CRITICAL", "critical": "CRITICAL",
    "high": "HIGH", "medium": "MEDIUM", "moderate": "MEDIUM", "low": "LOW",
}
_TOKENS: Final = re.compile(r"https?://\S+|\b[\w-]+(?:\.[\w-]+)+\b|\d+")

SIGNAL_LABELS: Final = {
    SignalName.URGENCY: "pressure to act fast",
    SignalName.THREAT: "a threat",
    SignalName.SECRECY: "a demand for secrecy",
    SignalName.AUTHORITY_IMPERSONATION: "a claim to be an official or a bank",
    SignalName.CREDENTIAL_REQUEST: "a request for an OTP, PIN, or password",
    SignalName.PAYMENT_REQUEST: "a request for money",
    SignalName.APP_INSTALL_REQUEST: "a request to install an app",
    SignalName.REWARD_PROMISE: "a promise of money or a prize",
    SignalName.ADVANCE_FEE: "a fee to be paid first",
    SignalName.EMOTIONAL_PRESSURE: "emotional pressure",
    SignalName.LINK_PRESENT: "a link",
    SignalName.UNKNOWN_SENDER_CLAIM: "a claim of a new number",
    SignalName.SEXTORTION_THREAT: "a threat to share private images",
    SignalName.MONEY_MULE_REQUEST: "a request to use your bank account or SIM",
    SignalName.MONEY_GAME: "a real-money game or betting offer",
}
_OVERRIDE_TEXT: Final = {
    "urgent_recovery": "You said money was sent or secret details were shared.",
    "child_safety": "The case may involve a child and private images.",
    "blocklist_floor": "A link, number, or ID is on the ScamSaathi demo blocklist.",
}
HEADLINES: Final = {
    "en": {
        "CRITICAL": "Very high risk: this looks like a scam. Do not pay, share codes, or reply.",
        "HIGH": "High risk: this shows strong signs of a scam.",
        "MEDIUM": "Medium risk: there are warning signs. Verify before you act.",
        "LOW": "Low risk: no strong scam signs were found, but stay careful.",
    },
    "hinglish": {
        "CRITICAL": "Bahut zyada risk: yeh scam lagta hai. Paise mat bhejiye, code mat batayiye.",
        "HIGH": "Zyada risk: isme scam ke saaf nishaan hain.",
        "MEDIUM": "Medium risk: kuch warning signs hain. Pehle verify kijiye.",
        "LOW": "Kam risk: scam ke bade nishaan nahi mile, phir bhi savdhaan rahiye.",
    },
}
UNCERTAINTY: Final = {
    "en": ("ScamSaathi cannot see who contacted you or verify the sender. Check through the "
           "organisation's official app or website, or the number printed on your card."),
    "hinglish": ("ScamSaathi yeh nahi dekh sakta ki aapse kisne sampark kiya. Organisation ke "
                 "official app, website ya card par chhape number se verify kijiye."),
}


def _clean(text: str) -> bool:
    return bool(text.strip()) and not _BANNED.search(text) and not _LEGAL.search(text)


def headline_ok(headline: str, level: str) -> bool:
    if not _clean(headline):
        return False
    return all(_LEVEL_OF[m.lower()] == level for m in _LEVEL_MENTION.findall(headline))


def action_ok(reworded: str, original: str) -> bool:
    """Reworded advice must keep exactly the same numbers and links (none added, none
    dropped, so reporting channels and helplines survive rewording) and must not ask for
    secrets."""
    if not _clean(reworded):
        return False
    if set(_TOKENS.findall(reworded.lower())) != set(_TOKENS.findall(original.lower())):
        return False
    names = {s.name for s in rule_signals.detect(reworded, has_link=False)}
    return SignalName.CREDENTIAL_REQUEST not in names


# --- Evidence catalogue ---------------------------------------------------------------


def evidence_catalogue(state: ScamState, ctx: AgentContext, risk: RiskScore) -> dict[str, str]:
    items: dict[str, str] = {}
    for s in state.get("signals", []):
        sig = Signal.model_validate(s)
        items[sig.evidence_id] = f'{SIGNAL_LABELS[sig.name]}: "{sig.evidence_span}"'
    intel = read(state, "intel", IntelResult) or IntelResult()
    for f in intel.findings:
        items[f.evidence_id] = f.detail
    chunks = {c.chunk_id: c for c in ctx.kb.chunks}
    for i, cid in enumerate(state.get("kb_chunk_ids", []), start=1):
        if cid in chunks:
            items[f"K{i}"] = f"{chunks[cid].name}: {chunks[cid].text[:300]}"
    for i, override in enumerate(risk.overrides, start=1):
        items[f"C{i}"] = _OVERRIDE_TEXT.get(override, override)
    if not any(k[0] in "SIC" for k in items):
        # Knowledge excerpts describe scam types, so they must never be the only "reason"
        # for a message with no evidence against it.
        items["C1"] = "No warning signs were found by ScamSaathi's checks."
    return items


def template_explanation(risk: RiskScore, catalogue: dict[str, str], language: str,
                         typology_names: list[str]) -> Explanation:
    lang = "en"
    headline = HEADLINES[lang][risk.level]
    if typology_names and risk.level != "LOW":
        headline += f" It looks like: {typology_names[0]}."
    reasons: list[Reason] = []
    seen: set[str] = set()
    overrides = [k for k in catalogue if k.startswith("C")]
    for key in overrides:
        reasons.append(Reason(text=catalogue[key], evidence_ids=[key]))
        seen.add(key)
    for c in sorted(risk.contributions, key=lambda c: -abs(c.points)):
        if c.factor.startswith(("combo:", "classification:")) or not c.evidence_ids:
            continue
        key = c.evidence_ids[0]
        if key in seen or key not in catalogue:
            continue
        prefix = "The message shows " if key.startswith("S") else ""
        reasons.append(Reason(text=prefix + catalogue[key], evidence_ids=[key]))
        seen.add(key)
        if len(reasons) >= 4:
            break
    if not reasons:
        key = next(iter(catalogue))
        reasons.append(Reason(text=catalogue[key], evidence_ids=[key]))
    return Explanation(headline=headline, reasons=reasons[:4], uncertainty=UNCERTAINTY[lang])


# --- LLM output -----------------------------------------------------------------------


class ReasonOut(BaseModel):
    text: str = Field(min_length=3, max_length=300)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)


class ExplainOutput(BaseModel):
    headline: str = Field(min_length=3, max_length=200)
    reasons: list[ReasonOut] = Field(min_length=1, max_length=5)
    uncertainty: str = Field(min_length=3, max_length=300)
    actions: list[str] = Field(default_factory=list, max_length=25)


def merge_llm(out: ExplainOutput, template: Explanation, advice: AdviceBundle, level: str,
              catalogue: dict[str, str]) -> tuple[Explanation, AdviceBundle, list[str]]:
    """Accept each LLM field only if it passes validation; report what was rejected."""
    rejected: list[str] = []
    headline = out.headline.strip()
    if not headline_ok(headline, level):
        headline, rejected = template.headline, [*rejected, "headline"]
    reasons = [
        Reason(text=r.text.strip(), evidence_ids=[i for i in dict.fromkeys(r.evidence_ids)])
        for r in out.reasons
        if r.evidence_ids and set(r.evidence_ids) <= set(catalogue) and _clean(r.text)
    ][:4]
    if len(reasons) < len(out.reasons):
        rejected.append("reasons")
    if not reasons:
        reasons = template.reasons
    uncertainty = out.uncertainty.strip()
    if not _clean(uncertainty):
        uncertainty, rejected = template.uncertainty, [*rejected, "uncertainty"]

    actions = advice.actions
    if len(out.actions) == len(advice.actions):
        reworded = [
            Action(priority=a.priority, text=new.strip() if action_ok(new, a.text) else a.text)
            for a, new in zip(advice.actions, out.actions, strict=True)
        ]
        if any(r.text != new.strip() for r, new in zip(reworded, out.actions, strict=True)):
            rejected.append("actions")
        actions = reworded
    elif out.actions:
        rejected.append("actions")
    explanation = Explanation(headline=headline, reasons=reasons, uncertainty=uncertainty)
    return explanation, advice.model_copy(update={"actions": actions}), rejected


def telemarketing_number(state: ScamState) -> bool:
    """A TRAI 140-series number or a promotional (-P) sender header appeared (FR-085)."""
    for e in state.get("entities", []):
        if e["kind"] == "sender_header" and e["masked"].endswith("-P"):
            return True
        if "designated_series" in e.get("flags", []):
            digits = re.sub(r"\D", "", e["masked"])[-10:]
            if digits.startswith("140"):
                return True
    return False


def explain_advise(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    risk = RiskScore.model_validate(state["score"])
    situation = read(state, "situation", Situation) or Situation()
    codes = state.get("typologies", [])
    advice = build_advice(ctx.kb, risk.level, codes, situation, telemarketing_number(state))
    language = state.get("language", "en")
    names = [ctx.kb.typologies[c].name for c in codes if c in ctx.kb.typologies]
    catalogue = evidence_catalogue(state, ctx, risk)
    template = template_explanation(risk, catalogue, language, names)

    reply_language = "english"
    user = "\n".join([
        f"RISK_LEVEL: {risk.level}",
        "EVIDENCE: " + json.dumps(catalogue, ensure_ascii=False),
        "TYPOLOGIES: " + json.dumps(names, ensure_ascii=False),
        "ACTIONS: " + json.dumps([a.text for a in advice.actions], ensure_ascii=False),
        f"LANGUAGE: {reply_language}",
        untrusted_block(case_text(state)),
    ])
    result, update = ctx.call_llm(state, node="explain", prompt=load_prompt("explain"),
                                  tier="reasoning", user=user, schema=ExplainOutput)
    if result is None:
        explanation, source = template, "template"
    else:
        explanation, advice, rejected = merge_llm(result.output, template, advice, risk.level,
                                                  catalogue)
        source = "llm"
        if rejected:
            update["errors"] = [*update.get("errors", []),
                                f"explain: rejected LLM {', '.join(rejected)}"]
    update.update({
        "explanation": dump(explanation),
        "advice": dump(advice),
        "explanation_source": source,
        "evidence_catalogue": catalogue,
    })
    return update
