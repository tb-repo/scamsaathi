"""Shared data contracts (task 1.3). Mirrors docs/06-tool-specifications.md section 2."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Language(StrEnum):
    EN = "en"
    HINGLISH = "hinglish"
    HI = "hi"
    OTHER = "other"


class InputMode(StrEnum):
    MESSAGE = "message"
    SITUATION = "situation"
    ENTITY_QUERY = "entity_query"


class SignalName(StrEnum):
    """Fixed behavioural signal vocabulary (docs/05, A2)."""

    URGENCY = "urgency"
    THREAT = "threat"
    SECRECY = "secrecy"
    AUTHORITY_IMPERSONATION = "authority_impersonation"
    CREDENTIAL_REQUEST = "credential_request"
    PAYMENT_REQUEST = "payment_request"
    APP_INSTALL_REQUEST = "app_install_request"
    REWARD_PROMISE = "reward_promise"
    ADVANCE_FEE = "advance_fee"
    EMOTIONAL_PRESSURE = "emotional_pressure"
    LINK_PRESENT = "link_present"
    UNKNOWN_SENDER_CLAIM = "unknown_sender_claim"
    # Added after the legal-source review (docs/16 section 10).
    SEXTORTION_THREAT = "sextortion_threat"
    MONEY_MULE_REQUEST = "money_mule_request"
    MONEY_GAME = "money_game"


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
# "sender_header": a TRAI DLT SMS header such as "AX-HDFCBK-S" (organisation name, not PII).
EntityKind = Literal[
    "url", "phone", "upi", "email", "amount", "account_like", "id_number", "sender_header"
]
Severity = Literal["info", "low", "medium", "high"]


EntityFlag = Literal["international", "designated_series"]


class Entity(_Model):
    kind: EntityKind
    value_ref: str  # key into the in-memory map; never the raw value
    masked: str  # e.g. "<PHONE_1>"; designated-series numbers and headers stay visible
    span: tuple[int, int]
    flags: list[EntityFlag] = Field(default_factory=list)


class Signal(_Model):
    name: SignalName
    confidence: float = Field(ge=0, le=1)
    evidence_span: str
    evidence_id: str


class SignalSet(_Model):
    entities: list[Entity] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    impersonated_org: str | None = None


class IntelFinding(_Model):
    entity_ref: str
    check: str
    severity: Severity
    detail: str
    evidence_id: str


class IntelResult(_Model):
    findings: list[IntelFinding] = Field(default_factory=list)
    degraded: bool = False


class TypologyMatch(_Model):
    code: str = Field(pattern=r"^SC-\d{2}$")
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class ClassificationResult(_Model):
    matches: list[TypologyMatch] = Field(default_factory=list)
    needs_more_info: bool = False
    missing_facts: list[str] = Field(default_factory=list)
    kb_chunk_ids: list[str] = Field(default_factory=list)


class Contribution(_Model):
    factor: str
    points: float
    evidence_ids: list[str] = Field(default_factory=list)


class RiskScore(_Model):
    value: int = Field(ge=0, le=100)
    level: RiskLevel
    contributions: list[Contribution] = Field(default_factory=list)
    overrides: list[str] = Field(default_factory=list)
    llm_adjustment: int = Field(default=0, ge=-10, le=10)
    llm_adjustment_reason: str | None = None


class Reason(_Model):
    text: str
    evidence_ids: list[str] = Field(min_length=1)


class Explanation(_Model):
    headline: str
    reasons: list[Reason]
    uncertainty: str


class Action(_Model):
    priority: int = Field(ge=1)
    text: str


class OfficialContact(_Model):
    name: str
    channel: Literal["phone", "url"]
    value: str
    verified_on: str  # ISO date


class AdviceBundle(_Model):
    actions: list[Action] = Field(default_factory=list)
    contacts: list[OfficialContact] = Field(default_factory=list)
    complaint_draft: str | None = None
    urgent_recovery_mode: bool = False


class GuardrailResult(_Model):
    passed: bool
    failures: list[str] = Field(default_factory=list)


# --- Agent graph (Phase 4) -------------------------------------------------------------

# Facts the interview can ask about (docs/05 A5). Each maps to one static question and,
# when answered "yes", to a sentence the rule-based extractor understands.
MissingFact = Literal[
    "asked_for_secret",
    "asked_to_pay",
    "asked_to_install_app",
    "asked_secrecy",
    "claimed_authority",
    "threatened",
    "urgency",
    "money_sent",
    "secret_shared",
    "link_clicked",
]


class PrescreenResult(_Model):
    """Deterministic quick classification (docs/05 A4 pre-screen)."""

    confidence: float = Field(ge=0, le=1)
    provisional_level: RiskLevel
    provisional_value: int = Field(ge=0, le=100)
    reason: str
    # True only when the classifier cannot improve the result: a genuine message verified by
    # intel, or the child-safety path (fixed advice). Scam cases always get the classifier,
    # because the typology chooses the advice and contacts (ADR-001 addendum: quality first).
    skip_classifier: bool = False
