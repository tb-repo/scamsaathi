"""A5 Interview, static question bank (graph wiring for tasks 4.1 and 5.1; FR-040 to FR-043).

Two nodes, following the ADR-002 spike rules:
- ``plan_questions`` picks questions (no side effects, no interrupt).
- ``await_answers`` pauses with ``interrupt()``. Code before the interrupt re-runs on
  resume, so it only reads state.

Answers can be ``{"answers": {fact: true/false}, "text": "..."}``, a plain string, or
``"skip"``. A "yes" becomes a fixed sentence that the rule-based extractor understands,
so the effect of each answer is deterministic and testable. Free text is masked again here
as defence in depth. Callers must still mask before resuming, because LangGraph stores the
resume value itself (``AgentRunner.resume`` does this).

Questions never ask for an OTP, PIN, password, card or account number (FR-064).
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState, case_text
from scamsaathi.prompts import load_prompt, untrusted_block
from scamsaathi.schemas import ClassificationResult
from scamsaathi.tools.pii_masker import mask

# fact -> (English question, Hinglish question, sentence added when the answer is yes)
QUESTION_BANK: Final[dict[str, tuple[str, str, str]]] = {
    "asked_for_secret": (
        "Did they ask you to share an OTP, PIN, or password?",
        "Kya unhone OTP, PIN ya password maanga?",
        "They asked me to share my OTP or PIN.",
    ),
    "asked_to_pay": (
        "Did they ask you to pay or transfer money?",
        "Kya unhone paise bhejne ya pay karne ko kaha?",
        "They asked me to pay money.",
    ),
    "asked_to_install_app": (
        "Did they ask you to install an app, such as AnyDesk or an APK file?",
        "Kya unhone koi app install karne ko kaha, jaise AnyDesk ya APK file?",
        "They asked me to install an app like AnyDesk.",
    ),
    "asked_secrecy": (
        "Did they tell you not to tell anyone, or to stay on the call?",
        "Kya unhone kaha ki kisi ko mat batana, ya call par bane rahna?",
        "They told me: do not tell anyone.",
    ),
    "claimed_authority": (
        "Did they say they were from the police, a court, a government office, or a bank?",
        "Kya unhone kaha ki woh police, court, sarkari office ya bank se hain?",
        "They said they were from the police, a bank or the government.",
    ),
    "threatened": (
        "Did they threaten to block your account, cut your service, or arrest you?",
        "Kya unhone account block karne, service band karne ya giraftar karne ki dhamki di?",
        "They threatened that my account would be blocked or I would be arrested.",
    ),
    "urgency": (
        "Did they say you must act right now?",
        "Kya unhone kaha ki abhi ke abhi karna hoga?",
        "They said I must act right now.",
    ),
    "money_sent": (
        "Have you already sent any money?",
        "Kya aapne pehle hi koi paise bhej diye hain?",
        "I already paid them.",
    ),
    "secret_shared": (
        "Have you already shared an OTP, PIN, or password with them?",
        "Kya aapne unhe OTP, PIN ya password bata diya hai?",
        "I already shared the OTP.",
    ),
    "link_clicked": (
        "Did you already click a link they sent?",
        "Kya aapne unka bheja hua link khol diya?",
        "I already clicked the link.",
    ),
}
_YES: Final = re.compile(r"^\s*(?:yes|y|yeah|yep|haan|han|ha|ji haan|ji|true)\b", re.I)
_NO: Final = re.compile(r"^\s*(?:no|n|nope|nahi|nahin|na|false)\b", re.I)
SKIP_WORDS: Final = frozenset({"skip", "skip it", "give me best assessment", "rehne do"})


_FORBIDDEN_SECRET_WORDS: Final = re.compile(
    r"\b(?:what is your|share your|tell me your|enter your|give me your)\s+(?:otp|pin|password|cvv|card\s*number)\b",
    re.I,
)


class GeneratedQuestion(BaseModel):
    fact: str
    text: str = Field(min_length=5, max_length=200)


class InterviewOutput(BaseModel):
    questions: list[GeneratedQuestion] = Field(default_factory=list, max_length=3)


def question_text(fact: str, language: str = "en") -> str:
    english, _, _ = QUESTION_BANK[fact]
    return english


def plan_questions(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    classification = ClassificationResult.model_validate(state.get("classification", {}))
    asked = set(state.get("asked_facts", []))
    facts = [f for f in classification.missing_facts if f in QUESTION_BANK and f not in asked]
    facts = facts[: ctx.routing.max_questions_per_turn]
    if not facts:
        return {"pending_questions": []}

    static_questions = [{"fact": f, "text": question_text(f)} for f in facts]

    # Task 5.1: Try contextual LLM-generated questions if configured, active, and within budget
    if ctx.routing.llm_interview_questions:
        user = (
            "MISSING_FACTS: "
            + json.dumps(facts)
            + "\nDEFAULT_QUESTIONS: "
            + json.dumps(static_questions)
            + "\n"
            + untrusted_block(case_text(state))
        )
        result, update = ctx.call_llm(
            state,
            node="interview",
            prompt=load_prompt("interview"),
            tier="fast",
            user=user,
            schema=InterviewOutput,
            reserve=ctx.routing.llm_reserve_for_explanation,
        )
        if result and result.output.questions:
            valid_map: dict[str, str] = {}
            for q in result.output.questions:
                if q.fact in facts and not _FORBIDDEN_SECRET_WORDS.search(q.text):
                    valid_map[q.fact] = q.text.strip()
            merged: list[dict[str, str]] = []
            for sq in static_questions:
                f = sq["fact"]
                merged.append({"fact": f, "text": valid_map.get(f, sq["text"])})
            return {"pending_questions": merged[: ctx.routing.max_questions_per_turn]}

    return {"pending_questions": static_questions}


def _interpret(answer: Any, pending: list[dict[str, str]]) -> tuple[list[str], bool]:
    """Return (new masked answer lines, skipped)."""
    facts = [q["fact"] for q in pending]
    yes: dict[str, bool] = {}
    free = ""
    if isinstance(answer, dict):
        if answer.get("skip"):
            return [], True
        yes = {k: bool(v) for k, v in (answer.get("answers") or {}).items() if k in facts}
        free = str(answer.get("text") or "")
    else:
        free = str(answer or "")
        if free.strip().lower() in SKIP_WORDS:
            return [], True
        if len(facts) == 1 and (_YES.match(free) or _NO.match(free)):
            yes = {facts[0]: bool(_YES.match(free))}
    lines = [QUESTION_BANK[f][2] for f in facts if yes.get(f)]
    if free.strip():
        lines.append(mask(free.strip()[:1000]).masked_text)
    return lines, False


def await_answers(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    pending = state.get("pending_questions", [])
    answer = interrupt({"questions": pending, "can_skip": True})
    # Everything below runs only after resume.
    lines, skipped = _interpret(answer, pending)
    return {
        "user_answers": [*state.get("user_answers", []), *lines],
        "asked_facts": [*state.get("asked_facts", []), *(q["fact"] for q in pending)],
        "followups_asked": state.get("followups_asked", 0) + 1,
        "pending_questions": [],
        "interview_skipped": skipped,
    }
