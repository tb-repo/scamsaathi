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


def test_mixed_answer_otp_nobody_used_it(runner: AgentRunner) -> None:
    text = "I heard the caller shared my OTP with another person"
    first = runner.assess(text)
    assert first.status == "needs_followup"

    # User answers with mixed context: code belongs to them, but was not used/compromised
    resumed = runner.resume(first.thread_id, "code is mine, but nobody used it")
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level == "LOW"
    assert "urgent_recovery" not in resumed.risk.overrides
    assert resumed.advice is not None
    assert not resumed.advice.urgent_recovery_mode
    runner.clear_session(first.thread_id, purge_checkpoint=True)


def test_mixed_answer_apk_no_remote_access(runner: AgentRunner) -> None:
    apk_text = "The technician may have installed an APK on my phone"
    first = runner.assess(apk_text)
    assert first.status == "needs_followup"

    # User answers: app is on phone, but no remote access/permissions granted
    resumed = runner.resume(first.thread_id, "app is on my phone, but I granted no remote access")
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level == "LOW"
    assert "urgent_recovery" not in resumed.risk.overrides
    assert resumed.advice is not None
    assert not resumed.advice.urgent_recovery_mode
    runner.clear_session(first.thread_id, purge_checkpoint=True)


def test_mixed_answer_unauthorized_debit_noticed(runner: AgentRunner) -> None:
    text = "I heard the caller shared my OTP with another person"
    first = runner.assess(text)
    assert first.status == "needs_followup"

    # User confirms noticing an unauthorized debit
    resumed = runner.resume(first.thread_id, "yes, I noticed an unauthorized debit")
    assert resumed.status == "complete"
    assert resumed.risk is not None
    assert resumed.risk.level in ("HIGH", "CRITICAL")
    assert resumed.risk.value >= 60
    assert "urgent_recovery" in resumed.risk.overrides
    assert resumed.advice is not None
    assert resumed.advice.urgent_recovery_mode
    assert "1930" in resumed.advice.actions[0].text
    runner.clear_session(first.thread_id, purge_checkpoint=True)


def test_otp_caller_already_had_it_triggers_urgent_recovery(runner: AgentRunner) -> None:
    text = "I did not share my OTP, but the caller already had it"
    outcome = runner.assess(text)
    assert outcome.status == "complete"
    assert outcome.risk is not None
    assert outcome.risk.level in ("HIGH", "CRITICAL")
    assert outcome.risk.value >= 60
    assert "urgent_recovery" in outcome.risk.overrides
    assert outcome.advice is not None
    assert outcome.advice.urgent_recovery_mode
    assert any("1930" in a.text or "freeze" in a.text.lower() for a in outcome.advice.actions)
    runner.clear_session(outcome.thread_id, purge_checkpoint=True)


def test_technician_apk_unauthorized_installation_tracked(runner: AgentRunner) -> None:
    text = "The technician installed an APK on my phone without asking me"
    outcome = runner.assess(text)
    if outcome.status == "needs_followup":
        outcome = runner.resume(outcome.thread_id, {"skip": True})
    assert outcome.status == "complete"
    snap = runner.graph.get_state(runner._config(outcome.thread_id))
    sit = snap.values.get("situation", {})
    assert sit.get("app_installed") is True
    app_exp = sit.get("app_installation", {})
    assert app_exp.get("status") == "confirmed"
    assert app_exp.get("actor") == "third_party"
    assert app_exp.get("target") == "user_device"
    assert app_exp.get("authorized") == "denied"
    runner.clear_session(outcome.thread_id, purge_checkpoint=True)

def test_technician_inquiry_apk_denial_no_urgent_recovery(runner: AgentRunner) -> None:
    text = "The technician asked whether I installed the APK, but I said no"
    outcome = runner.assess(text)
    if outcome.status == "needs_followup":
        outcome = runner.resume(outcome.thread_id, {"skip": True})
    assert outcome.status == "complete"
    assert outcome.risk is not None
    assert "urgent_recovery" not in outcome.risk.overrides
    snap = runner.graph.get_state(runner._config(outcome.thread_id))
    sit = snap.values.get("situation", {})
    assert sit.get("app_installed") is False
    assert sit.get("app_installation", {}).get("status") == "denied"
    runner.clear_session(outcome.thread_id, purge_checkpoint=True)


def test_user_had_otp_on_phone_not_third_party_exposure(runner: AgentRunner) -> None:
    text = "I already had my OTP on my phone"
    outcome = runner.assess(text)
    if outcome.status == "needs_followup":
        outcome = runner.resume(outcome.thread_id, {"skip": True})
    assert outcome.status == "complete"
    assert outcome.risk is not None
    assert "urgent_recovery" not in outcome.risk.overrides
    snap = runner.graph.get_state(runner._config(outcome.thread_id))
    sit = snap.values.get("situation", {})
    assert sit.get("credentials_shared") is False
    assert sit.get("credentials_exposure", {}).get("status") != "confirmed"
    runner.clear_session(outcome.thread_id, purge_checkpoint=True)
