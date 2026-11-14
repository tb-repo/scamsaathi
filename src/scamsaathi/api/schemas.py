"""FastAPI Pydantic Schemas for ScamSaathi REST API (FR-070)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

STANDARD_DISCLAIMER = (
    "ScamSaathi provides risk assessments for guidance only. It is not a legal or definitive "
    "determination. Automated masking protects phone numbers, accounts, UPI IDs, and OTPs, "
    "but cannot reliably redact personal names or street addresses. Always verify independently through official channels."
)


class AssessRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="Pasted suspicious message or call transcript")
    thread_id: str | None = Field(default=None, description="Optional thread/session ID")


class ResumeRequest(BaseModel):
    thread_id: str = Field(min_length=1, description="Existing thread/session ID")
    answer: str | dict[str, Any] = Field(description="User answer ('yes', 'no', 'skip', or dict with details)")


class ActionOut(BaseModel):
    priority: int
    text: str


class OfficialContactOut(BaseModel):
    name: str
    channel: str
    value: str
    verified_on: str


class ReasonOut(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)


class ExplanationOut(BaseModel):
    headline: str
    reasons: list[ReasonOut] = Field(default_factory=list)
    uncertainty: str


class AssessResponse(BaseModel):
    thread_id: str
    status: Literal["needs_followup", "complete"]
    risk_level: str | None = None
    risk_score: int | None = None
    headline: str | None = None
    reasons: list[ReasonOut] = Field(default_factory=list)
    actions: list[ActionOut] = Field(default_factory=list)
    contacts: list[OfficialContactOut] = Field(default_factory=list)
    questions: list[dict[str, str]] = Field(default_factory=list)
    typologies: list[str] = Field(default_factory=list)
    language: str = "en"
    disclaimer: str = STANDARD_DISCLAIMER
    degraded: bool = False
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    mode: str
    primary_provider: str
    primary_model_fast: str
    primary_model_reasoning: str
    fallback_provider: str | None = None
    fallback_model_fast: str | None = None
    fallback_model_reasoning: str | None = None
    disclaimer: str = STANDARD_DISCLAIMER

