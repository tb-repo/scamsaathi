"""Graph state and routing configuration (task 4.1; docs/04 section 5, docs/05 A0).

State values are plain JSON-compatible data (dicts, lists, strings, numbers). Pydantic
models are dumped on write and validated on read, so the checkpointer never has to
deserialise custom classes. State holds **masked data only** (ADR-007): no raw text, no
PII map, no unmasked entities.
"""

from __future__ import annotations

import operator
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, TypedDict, TypeVar

from pydantic import BaseModel, Field

from scamsaathi.config import CONFIG_DIR, load_yaml

M = TypeVar("M", bound=BaseModel)


class ScamState(TypedDict, total=False):
    request_id: str
    masked_text: str
    language: str  # Language value
    input_mode: str  # InputMode value
    entities: list[dict[str, Any]]  # Entity
    signals: list[dict[str, Any]]  # Signal
    impersonated_org: str | None
    intel: dict[str, Any]  # IntelResult
    situation: dict[str, Any]  # Situation
    prescreen: dict[str, Any]  # PrescreenResult
    candidates: list[dict[str, Any]]  # [{"code": "SC-02", "score": 0.03}] from retrieval
    kb_chunk_ids: list[str]  # retrieved chunk IDs; K1 = first
    classification: dict[str, Any]  # ClassificationResult
    classification_source: str  # "llm" or "retrieval"
    llm_adjustment: dict[str, Any] | None  # LLMAdjustment
    followups_asked: int
    pending_questions: list[dict[str, str]]  # [{"fact": ..., "text": ...}]
    asked_facts: list[str]
    user_answers: list[str]  # masked
    interview_skipped: bool
    score: dict[str, Any]  # RiskScore
    explanation: dict[str, Any]  # Explanation
    explanation_source: str  # "llm" or "template"
    advice: dict[str, Any]  # AdviceBundle
    typologies: list[str]  # final typology codes, best first
    llm_calls: int
    errors: Annotated[list[str], operator.add]
    degraded: bool


def read(state: ScamState, key: str, model: type[M]) -> M | None:
    """Validate a stored dict back into its model, or None if absent."""
    value = state.get(key)
    return None if value is None else model.model_validate(value)


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def case_text(state: ScamState) -> str:
    """Masked message plus masked interview answers: the text the agents analyse."""
    answers = state.get("user_answers", [])
    if not answers:
        return state.get("masked_text", "")
    return "\n".join([state.get("masked_text", ""), *(f"User answer: {a}" for a in answers)])


class RoutingConfig(BaseModel):
    version: int
    prescreen_high_confidence: float = Field(ge=0, le=1)
    max_followups: int = Field(ge=0, le=5)
    max_questions_per_turn: int = Field(ge=1, le=5)
    llm_reserve_for_explanation: int = Field(ge=0, le=3)
    max_input_chars: int = Field(ge=100)
    recursion_limit: int = Field(ge=10)
    llm_interview_questions: bool = Field(default=False)


@lru_cache(maxsize=4)
def load_routing_config(path: Path = CONFIG_DIR / "routing.yaml") -> RoutingConfig:
    return RoutingConfig.model_validate(load_yaml(path))
