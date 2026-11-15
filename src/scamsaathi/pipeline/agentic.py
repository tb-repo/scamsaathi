"""Agentic pipeline entry point (tasks 4.1 and 4.6). Used by scripts now, by the API in Phase 6.

``AgentRunner.assess`` registers the original text in the vault for one ``invoke`` and
removes it afterwards, whatever happens. ``AgentRunner.resume`` masks answers *before*
they reach LangGraph, because LangGraph stores resume values in the checkpoint.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from scamsaathi.agents.context import AgentContext, RawRequest
from scamsaathi.agents.guardrails import GuardrailAgent
from scamsaathi.graph.builder import build_graph
from scamsaathi.schemas import AdviceBundle, Explanation, IntelResult, RiskScore, Signal
from scamsaathi.tools.pii_masker import mask


@dataclass(frozen=True)
class AssessmentOutcome:
    """Masked, user-safe result of one graph run."""

    thread_id: str
    status: Literal["needs_followup", "complete"]
    questions: list[dict[str, str]] = field(default_factory=list)
    risk: RiskScore | None = None
    explanation: Explanation | None = None
    advice: AdviceBundle | None = None
    typologies: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    intel: IntelResult | None = None
    language: str = "en"
    input_mode: str = "message"
    explanation_source: str = ""
    llm_calls: int = 0
    degraded: bool = False
    errors: list[str] = field(default_factory=list)
    masked_text: str = ""
    catalogue: dict[str, str] = field(default_factory=dict)


class AgentRunner:
    def __init__(self, ctx: AgentContext, checkpointer: BaseCheckpointSaver[Any] | None = None):
        self.ctx = ctx
        self.guardrail = GuardrailAgent(ctx)
        self.graph = build_graph(ctx, checkpointer or InMemorySaver())
        self._session_mappings: dict[str, dict[str, str]] = {}
        self._session_created_at: dict[str, float] = {}

    def _config(self, thread_id: str) -> Any:
        return {"configurable": {"thread_id": thread_id},
                "recursion_limit": self.ctx.routing.recursion_limit}

    def assess(self, text: str, thread_id: str | None = None) -> AssessmentOutcome:
        self.cleanup_abandoned_sessions()
        text = (text or "").strip()
        if not text:
            raise ValueError("input text is empty")
        if len(text) > self.ctx.routing.max_input_chars:
            raise ValueError(f"input is longer than {self.ctx.routing.max_input_chars} characters")
        thread_id = thread_id or uuid.uuid4().hex
        raw = RawRequest(text=text)
        self.ctx.vault.put(thread_id, raw)
        try:
            self.graph.invoke({"request_id": thread_id}, self._config(thread_id))
            if raw.mask is not None:
                self._session_mappings[thread_id] = dict(raw.mask.mapping)
                self._session_created_at[thread_id] = time.time()
            outcome = self.outcome(thread_id)
            if outcome.status != "needs_followup":
                self.clear_session(thread_id)
            return outcome
        except Exception:
            self.clear_session(thread_id)
            raise
        finally:
            self.ctx.vault.pop(thread_id)  # originals never outlive the request

    def resume(self, thread_id: str, answer: str | dict[str, Any]) -> AssessmentOutcome:
        mapping = self._session_mappings.get(thread_id)
        if isinstance(answer, str):
            masked = mask(answer[:1000], existing_mapping=mapping)
            if mapping is not None:
                mapping.update(masked.mapping)
            safe: str | dict[str, Any] = masked.masked_text
        else:
            text_val = str(answer.get("text") or "")[:1000]
            masked = mask(text_val, existing_mapping=mapping)
            if mapping is not None:
                mapping.update(masked.mapping)
            safe = {
                "skip": bool(answer.get("skip")),
                "answers": {str(k): bool(v) for k, v in (answer.get("answers") or {}).items()},
                "text": masked.masked_text,
            }
        try:
            self.graph.invoke(Command(resume=safe), self._config(thread_id))
            outcome = self.outcome(thread_id)
            if outcome.status != "needs_followup":
                self.clear_session(thread_id)
            return outcome
        except Exception:
            self.clear_session(thread_id)
            raise

    def outcome(self, thread_id: str) -> AssessmentOutcome:
        snapshot = self.graph.get_state(self._config(thread_id))
        values: dict[str, Any] = dict(snapshot.values)
        common: dict[str, Any] = {
            "thread_id": thread_id,
            "signals": [Signal.model_validate(s) for s in values.get("signals", [])],
            "intel": IntelResult.model_validate(values["intel"]) if "intel" in values else None,
            "language": values.get("language", "en"),
            "input_mode": values.get("input_mode", "message"),
            "llm_calls": values.get("llm_calls", 0),
            "degraded": values.get("degraded", False),
            "errors": list(values.get("errors", [])),
            "masked_text": values.get("masked_text", ""),
        }
        if snapshot.interrupts:
            payload = snapshot.interrupts[0].value or {}
            followup = AssessmentOutcome(
                status="needs_followup",
                questions=list(payload.get("questions", [])),
                **common,
            )
            return self.guardrail.sanitize(followup)
        complete = AssessmentOutcome(
            status="complete",
            risk=RiskScore.model_validate(values["score"]),
            explanation=Explanation.model_validate(values["explanation"]),
            advice=AdviceBundle.model_validate(values["advice"]),
            typologies=list(values.get("typologies", [])),
            explanation_source=values.get("explanation_source", ""),
            catalogue=dict(values.get("evidence_catalogue", {})),
            **common,
        )
        return self.guardrail.sanitize(complete)

    def clear_session(self, thread_id: str) -> bool:
        """Purge in-memory PII mappings and vault entries for the session (DPDP principle 6)."""
        self._session_created_at.pop(thread_id, None)
        popped = self._session_mappings.pop(thread_id, None) is not None
        self.ctx.vault.pop(thread_id)
        return popped

    def cleanup_abandoned_sessions(self, max_age_seconds: float = 1800.0) -> int:
        """Purge in-memory sessions abandoned in needs_followup past max_age_seconds."""
        now = time.time()
        expired = [tid for tid, ts in self._session_created_at.items() if now - ts > max_age_seconds]
        for tid in expired:
            self.clear_session(tid)
        return len(expired)
