from __future__ import annotations

import pytest

from scamsaathi.agents.context import build_context
from scamsaathi.config import get_settings
from scamsaathi.pipeline.agentic import AgentRunner


@pytest.fixture
def runner() -> AgentRunner:
    ctx = build_context(get_settings())
    return AgentRunner(ctx)


def test_hearsay_otp_multiturn_confirmation(runner: AgentRunner) -> None:
    text = "I heard the caller shared my OTP with another person"
    first = runner.assess(text)
    assert first.status == "needs_followup"
    assert any("account" in q["text"].lower() or "code" in q["text"].lower() for q in (first.questions or []))

    # Turn 2a: Confirm user's account was exposed
    resumed = runner.resume(
        first.thread_id,
        "Yes, the code was for my own personal account and someone else obtained or used it.",
    )
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level == "HIGH"
    assert resumed.risk.value >= 60
    assert "urgent_recovery" in resumed.risk.overrides
    assert resumed.advice is not None
    assert resumed.advice.urgent_recovery_mode
    assert "1930" in resumed.advice.actions[0].text
    runner.clear_session(first.thread_id, purge_checkpoint=True)


def test_hearsay_otp_multiturn_denial(runner: AgentRunner) -> None:
    text = "I heard the caller shared my OTP with another person"
    first = runner.assess(text)
    assert first.status == "needs_followup"

    # Turn 2b: Clarify/deny user's account was involved
    resumed = runner.resume(
        first.thread_id,
        "No, the code was not for my personal account and no one has access to my account.",
    )
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level == "LOW"
    assert "urgent_recovery" not in resumed.risk.overrides
    assert resumed.advice is not None
    assert not resumed.advice.urgent_recovery_mode
    runner.clear_session(first.thread_id, purge_checkpoint=True)


def test_hearsay_otp_multiturn_skip(runner: AgentRunner) -> None:
    text = "I heard the caller shared my OTP with another person"
    first = runner.assess(text)
    assert first.status == "needs_followup"

    # Turn 2c: User skips
    resumed = runner.resume(first.thread_id, "skip")
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level == "LOW"
    assert "urgent_recovery" not in resumed.risk.overrides
    assert resumed.advice is not None
    assert not resumed.advice.urgent_recovery_mode
    assert resumed.explanation is not None
    assert any(w in resumed.explanation.uncertainty.lower() for w in ("unconfirmed", "confirm", "cannot", "verify"))
    runner.clear_session(first.thread_id, purge_checkpoint=True)


def test_ambiguous_apk_multiturn_denial(runner: AgentRunner) -> None:
    apk_text = "The technician may have installed an APK on my phone"
    first = runner.assess(apk_text)
    assert first.status == "needs_followup"
    assert any("app" in q["text"].lower() or "apk" in q["text"].lower() for q in (first.questions or []))

    # Turn 2b: Clarify not installed on user's device
    resumed = runner.resume(
        first.thread_id,
        "No, the app was not installed on my device and no remote access was granted.",
    )
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level == "LOW"
    assert "urgent_recovery" not in resumed.risk.overrides
    runner.clear_session(first.thread_id, purge_checkpoint=True)
