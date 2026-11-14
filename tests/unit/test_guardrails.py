"""Unit tests for Agent A9 Guardrail (FR-060 to FR-065, NFR-019)."""

from __future__ import annotations

import pytest

from scamsaathi.agents.context import AgentContext, build_context
from scamsaathi.agents.guardrails import GuardrailAgent, GuardrailViolation
from scamsaathi.config import get_settings
from scamsaathi.pipeline.agentic import AssessmentOutcome
from scamsaathi.schemas import (
    Action,
    AdviceBundle,
    Contribution,
    Explanation,
    OfficialContact,
    Reason,
    RiskScore,
)


@pytest.fixture
def ctx() -> AgentContext:
    return build_context(get_settings())


@pytest.fixture
def guardrail(ctx: AgentContext) -> GuardrailAgent:
    return GuardrailAgent(ctx)


def test_clean_outcome_passes(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-1",
        status="complete",
        risk=RiskScore(value=85, level="CRITICAL", contributions=[]),
        explanation=Explanation(
            headline="Very high risk: this looks like a scam.",
            reasons=[Reason(text="The message contains urgency and threats.", evidence_ids=["S1", "S2"])],
            uncertainty="ScamSaathi cannot see who contacted you.",
        ),
        advice=AdviceBundle(
            actions=[
                Action(priority=1, text="Stop all contact immediately and do not pay any money."),
                Action(priority=2, text="Report on Chakshu at https://sancharsaathi.gov.in/sfc within 30 days."),
            ],
            contacts=[
                OfficialContact(
                    name="Chakshu",
                    channel="url",
                    value="https://sancharsaathi.gov.in/sfc",
                    verified_on="2026-11-12",
                )
            ],
        ),
    )
    result = guardrail.verify(outcome)
    assert result.passed
    assert len(result.violations) == 0


def test_pii_leak_in_headline(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-2",
        status="complete",
        risk=RiskScore(value=85, level="CRITICAL", contributions=[]),
        explanation=Explanation(
            headline="High risk: call 9876543210 immediately to check.",
            reasons=[Reason(text="Urgent threat.", evidence_ids=["S1"])],
            uncertainty="Verify independently.",
        ),
        advice=AdviceBundle(actions=[], contacts=[]),
    )
    result = guardrail.verify(outcome)
    assert not result.passed
    assert any(v.code == "PII_LEAK" for v in result.violations)


def test_banned_claim_in_reason(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-3",
        status="complete",
        risk=RiskScore(value=10, level="LOW", contributions=[]),
        explanation=Explanation(
            headline="Low risk: no strong scam signs were found.",
            reasons=[Reason(text="This message is 100% safe and genuine.", evidence_ids=["C1"])],
            uncertainty="Verify independently.",
        ),
        advice=AdviceBundle(actions=[], contacts=[]),
    )
    result = guardrail.verify(outcome)
    assert not result.passed
    assert any(v.code == "BANNED_CLAIM" for v in result.violations)


def test_legal_section_cited(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-4",
        status="complete",
        risk=RiskScore(value=85, level="CRITICAL", contributions=[]),
        explanation=Explanation(
            headline="Critical risk: potential fraud.",
            reasons=[Reason(text="This violates Section 420 of the IPC.", evidence_ids=["S1"])],
            uncertainty="Verify independently.",
        ),
        advice=AdviceBundle(actions=[], contacts=[]),
    )
    result = guardrail.verify(outcome)
    assert not result.passed
    assert any(v.code == "LEGAL_SECTION" for v in result.violations)


def test_credential_request_in_action(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-5",
        status="complete",
        risk=RiskScore(value=85, level="CRITICAL", contributions=[]),
        explanation=Explanation(
            headline="Critical risk: potential fraud.",
            reasons=[Reason(text="Urgent threat.", evidence_ids=["S1"])],
            uncertainty="Verify independently.",
        ),
        advice=AdviceBundle(
            actions=[
                Action(priority=1, text="Please enter your OTP to confirm cancellation."),
            ],
            contacts=[],
        ),
    )
    result = guardrail.verify(outcome)
    assert not result.passed
    assert any(v.code == "CREDENTIAL_REQUEST" for v in result.violations)


def test_unverified_url_and_phone(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-6",
        status="complete",
        risk=RiskScore(value=85, level="CRITICAL", contributions=[]),
        explanation=Explanation(
            headline="Critical risk: potential fraud.",
            reasons=[Reason(text="Urgent threat.", evidence_ids=["S1"])],
            uncertainty="Verify independently.",
        ),
        advice=AdviceBundle(
            actions=[
                Action(priority=1, text="Visit https://random-scam-help-fake.com to get support."),
                Action(priority=2, text="Call our helpline at +919876543210."),
            ],
            contacts=[],
        ),
    )
    result = guardrail.verify(outcome)
    assert not result.passed
    assert any(v.code == "UNVERIFIED_URL" for v in result.violations)
    assert any(v.code == "UNVERIFIED_PHONE" for v in result.violations)


def test_risk_level_mismatch(guardrail: GuardrailAgent) -> None:
    outcome = AssessmentOutcome(
        thread_id="test-thread-7",
        status="complete",
        risk=RiskScore(value=85, level="CRITICAL", contributions=[]),
        explanation=Explanation(
            headline="Low risk: no signs of scam.",
            reasons=[Reason(text="No warnings.", evidence_ids=["C1"])],
            uncertainty="Verify independently.",
        ),
        advice=AdviceBundle(actions=[], contacts=[]),
    )
    result = guardrail.verify(outcome)
    assert not result.passed
    assert any(v.code == "RISK_LEVEL_MISMATCH" for v in result.violations)


def test_sanitize_fallback(guardrail: GuardrailAgent) -> None:
    bad_outcome = AssessmentOutcome(
        thread_id="test-thread-8",
        status="complete",
        risk=RiskScore(
            value=85,
            level="CRITICAL",
            contributions=[Contribution(factor="threat", points=40, evidence_ids=["S1"])],
        ),
        explanation=Explanation(
            headline="Low risk: this is 100% safe.",
            reasons=[Reason(text="Violates Section 420 IPC", evidence_ids=["S1"])],
            uncertainty="None",
        ),
        advice=AdviceBundle(
            actions=[Action(priority=1, text="Visit https://unverified-site.com")],
            contacts=[],
        ),
        typologies=["SC-01"],
    )
    sanitized = guardrail.sanitize(bad_outcome)
    assert sanitized.degraded
    assert len(sanitized.errors) > 0
    # Re-verify sanitized outcome
    second_check = guardrail.verify(sanitized)
    assert second_check.passed
