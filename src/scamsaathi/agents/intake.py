"""A1 Intake agent (task 4.2; FR-001 to FR-004, FR-060, FR-061).

Deterministic: masks PII, extracts entities, detects language and input mode, and reads
what the user says has already happened. Originals go to the vault, masked data to state.
No LLM call: the rule-based language detector is good enough for routing, and the
extraction prompt handles mixed language itself (docs/05 A1, "0 or 1 merged with A2").
"""

from __future__ import annotations

import re
from typing import Any, Final

from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState
from scamsaathi.schemas import InputMode
from scamsaathi.tools import rule_signals
from scamsaathi.tools.entities import RawEntity, extract
from scamsaathi.tools.language import detect
from scamsaathi.tools.pii_masker import mask
from scamsaathi.tools.risk_scorer import Situation

# First-person account of an event ("I got a call", "someone called me", "mujhe call aaya").
_NARRATIVE: Final = re.compile(
    r"\b(?:i|me|my|we|us|mujhe|maine|mera|meri|humein|hamein)\b.{0,40}?"
    r"\b(?:got|received|called|call(?:ed)? me|asked|said|told|sent|messaged|texted|"
    r"aaya|aayi|kaha|bola|boli|maanga|manga)\b|"
    r"\b(?:someone|somebody|a man|a woman|a person|they|koi)\b.{0,30}?"
    r"\b(?:called|messaged|texted|asked|said|told|call kiya)\b",
    re.I | re.S,
)
_WORD: Final = re.compile(r"\w+")


def input_mode(masked_text: str, entities: list[RawEntity]) -> InputMode:
    words = _WORD.findall(masked_text)
    identifiers = [e for e in entities if e.kind in ("url", "phone", "upi", "email", "sender_header")]
    if identifiers and len(words) <= 6:
        return InputMode.ENTITY_QUERY  # e.g. just a number or a link: "is this safe?"
    if _NARRATIVE.search(masked_text):
        return InputMode.SITUATION
    return InputMode.MESSAGE


def intake(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    request_id = state["request_id"]
    raw = ctx.vault.get(request_id)
    if raw is None:
        # Happens only if a caller invokes the graph without registering the text.
        return {"errors": ["intake: no input registered for this request"], "degraded": True,
                "masked_text": "", "entities": [], "situation": Situation().model_dump()}

    masked = mask(raw.text)
    entities = extract(raw.text, masked)
    raw.mask, raw.entities = masked, entities  # originals stay in the vault
    situation = Situation(**rule_signals.detect_situation(masked.masked_text))
    return {
        "masked_text": masked.masked_text,
        "language": detect(raw.text).language.value,
        "input_mode": input_mode(masked.masked_text, entities).value,
        "entities": [e.to_state().model_dump(mode="json") for e in entities],
        "situation": situation.model_dump(),
        "llm_calls": state.get("llm_calls", 0),
        "followups_asked": state.get("followups_asked", 0),
        "user_answers": state.get("user_answers", []),
        "asked_facts": state.get("asked_facts", []),
        "degraded": state.get("degraded", False),
    }
