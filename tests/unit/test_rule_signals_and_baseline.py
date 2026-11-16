"""Rule signals and the rules-only baseline B0 (task 2.7). All messages are synthetic."""

from __future__ import annotations

import pytest

from scamsaathi.config import PROJECT_ROOT
from scamsaathi.evaluation.labels import Case, check_behaviours, check_core, load_cases
from scamsaathi.pipeline.baseline import assess
from scamsaathi.schemas import SignalName
from scamsaathi.tools import rule_signals
from scamsaathi.tools.intel_db import IntelDB


def _names(text: str) -> set[SignalName]:
    return {s.name for s in rule_signals.detect(text)}


@pytest.mark.parametrize(
    "text",
    [
        "Please share the OTP you received",
        "OTP batao jaldi",
        "Send me your card CVV to verify",
        "Read out the verification code",
    ],
)
def test_credential_requests_detected(text: str) -> None:
    assert SignalName.CREDENTIAL_REQUEST in _names(text)


@pytest.mark.parametrize(
    "text",
    [
        "Your OTP is 482913. Do not share it with anyone.",
        "Never share your OTP or PIN with anyone, including bank staff.",
        "Apna OTP kisi ko mat batana",
    ],
)
def test_safety_notices_are_not_credential_requests(text: str) -> None:
    assert SignalName.CREDENTIAL_REQUEST not in _names(text)


def test_signals_have_evidence_from_masked_text() -> None:
    signals = rule_signals.detect("URGENT: account blocked, call <PHONE_1>")
    assert {s.name for s in signals} >= {SignalName.URGENCY, SignalName.THREAT}
    assert all(s.evidence_span and s.evidence_id.startswith("S") for s in signals)
    assert [s.evidence_id for s in signals] == [f"S{i}" for i in range(1, len(signals) + 1)]


def test_situation_detection() -> None:
    # Positive reporting detections
    assert rule_signals.detect_situation("I already paid Rs 5000")["money_sent"]
    assert rule_signals.detect_situation("I shared the OTP with him")["credentials_shared"]
    assert rule_signals.detect_situation("maine paise bhej diye")["money_sent"]
    assert rule_signals.detect_situation(
        "Maine call wale ko apna bank account number aur OTP dono bata diya hai"
    )["credentials_shared"]
    assert rule_signals.detect_situation(
        "abhi account se 40000 cut hone ka message aaya hai"
    )["money_sent"]
    paid_kyc = (
        "I followed a bank KYC link from a text and entered my banking password and "
        "one-time code. ₹18,000 has now left my account. What should I do immediately?"
    )
    sit_paid_kyc = rule_signals.detect_situation(paid_kyc)
    assert sit_paid_kyc["money_sent"]
    assert sit_paid_kyc["credentials_shared"]
    assert sit_paid_kyc["link_clicked"]

    # Positive mixed-clause tests (scoped event detection across contrastive boundaries)
    assert rule_signals.detect_situation(
        "I shared my OTP. I did not share my PIN."
    )["credentials_shared"]
    assert rule_signals.detect_situation(
        "I have not shared my OTP, but I gave the caller my banking password."
    )["credentials_shared"]
    assert rule_signals.detect_situation(
        "I have not shared my OTP, and I gave the caller my banking password."
    )["credentials_shared"]
    assert rule_signals.detect_situation(
        "What if I shared my OTP? I now confirm I shared it with the caller."
    )["credentials_shared"]
    assert rule_signals.detect_situation(
        "If I shared my OTP, I actually did share it with the caller."
    )["credentials_shared"]
    assert rule_signals.detect_situation(
        "Your account was debited INR 500; I already transferred another INR 2,000 to the fraudster."
    )["money_sent"]

    # Negative / false-positive guard tests (negations, hypotheticals, routine bank alerts)
    assert not rule_signals.detect_situation("I have not shared my OTP")["credentials_shared"]
    assert not rule_signals.detect_situation("I did not enter my password")["credentials_shared"]
    assert not rule_signals.detect_situation("Maine OTP nahi bataya")["credentials_shared"]
    assert not rule_signals.detect_situation(
        "If I entered my password and OTP, what should I do?"
    )["credentials_shared"]
    assert not rule_signals.detect_situation("What if I shared my PIN?")["credentials_shared"]
    assert not rule_signals.detect_situation(
        "Agar maine password de diya to kya hoga?"
    )["credentials_shared"]
    assert not rule_signals.detect_situation("I have not sent any money")["money_sent"]
    assert not rule_signals.detect_situation("I haven't paid anything")["money_sent"]
    assert not rule_signals.detect_situation("Maine paise nahi bheje")["money_sent"]
    assert not rule_signals.detect_situation(
        "If money left my account, what will happen?"
    )["money_sent"]
    assert not rule_signals.detect_situation("Do not click on suspicious links")["link_clicked"]
    assert not rule_signals.detect_situation(
        "HDFC Bank: INR 1,450.00 debited from your account XX4820 for AMAZON purchase"
    )["money_sent"]
    assert not rule_signals.detect_situation(
        "Dear Customer, your account XX1234 has been debited with INR 5,000.00"
    )["money_sent"]
    assert not rule_signals.detect_situation(
        "Salary of INR 82,500 credited to your account XX5120"
    )["money_sent"]
    assert not any(rule_signals.detect_situation("Got a message about my parcel").values())

    # Third-party action negative guards (actions performed by caller, technician, or third party)
    assert not rule_signals.detect_situation(
        "The caller provided an OTP to me for a demonstration."
    )["credentials_shared"]
    assert not rule_signals.detect_situation(
        "The caller clicked the link on their own phone, but I did not click it."
    )["link_clicked"]
    assert not rule_signals.detect_situation(
        "The technician installed an APK on their own device; I did not install it."
    )["app_installed"]
    assert not rule_signals.detect_situation("The caller clicked the link.")["link_clicked"]
    assert not rule_signals.detect_situation("The technician installed an APK.")["app_installed"]
    assert not rule_signals.detect_situation("The caller provided an OTP to me.")["credentials_shared"]


# Outcome checks for the rules-only baseline on the demo cases: scams must be warned about,
# genuine messages must not raise an alarm, and required behaviours must hold. These are
# sanity checks, not the evaluation (docs/09).
CASES = load_cases(PROJECT_ROOT / "data" / "demo" / "baseline_samples.jsonl")


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_baseline_outcomes(intel_db: IntelDB, case: Case) -> None:
    result = assess(case.text, intel_db)
    failures = check_core(case, result.risk, asked_questions=None) + check_behaviours(
        case, result.risk, advice=None, intel=result.intel, asked_questions=None
    )
    assert not failures, (case.id, failures, result.risk.value, result.risk.contributions)


def test_baseline_output_is_masked_and_traceable(intel_db: IntelDB) -> None:
    result = assess("URGENT: call 9000000001 and share OTP now", intel_db)
    dumped = repr(result)
    assert "9000000001" not in dumped
    assert "urgent_recovery" not in result.risk.overrides
    known_ids = {s.evidence_id for s in result.signals} | {
        f.evidence_id for f in result.intel.findings
    }
    for contribution in result.risk.contributions:
        assert set(contribution.evidence_ids) <= known_ids
    assert result.risk.level in {"HIGH", "CRITICAL"}  # blocklisted number => floor


def test_evaluate_pipeline_handles_runner_exception_without_unbound_local() -> None:
    from scripts.run_benchmarks import evaluate_pipeline

    case = Case(
        id="test_exc_case",
        text="Suspicious message",
        label="scam",
        language="en",
        typologies=["SC-01"],
        required=["report_channel"],
    )

    class FailingRunner:
        def assess(self, text: str) -> None:
            raise RuntimeError("Synthetic runner failure")

    metrics = evaluate_pipeline([case], runner=FailingRunner(), is_agentic=True)  # type: ignore[arg-type]
    assert metrics["eval_errors"] == 1
    assert metrics["cases"][0]["eval_error"] is True
    assert metrics["scams_total"] == 0
    assert metrics["scam_recall_warned"] is None
    assert metrics["behaviour_total"] == 0
    assert metrics["evaluated_cases"] == 0


def test_generate_markdown_report_warning_accuracy() -> None:
    from scripts.run_benchmarks import generate_markdown_report

    base_metrics = {
        "total_cases": 50,
        "evaluated_cases": 50,
        "eval_errors": 0,
        "scams_total": 36,
        "scam_recall_warned": 0.95,
        "scam_recall_high": 0.90,
        "legit_total": 14,
        "legit_clean": 13,
        "false_alarm_rate": 0.05,
        "behaviour_total": 36,
        "behaviour_ok": 36,
        "behaviour_rate": 1.0,
        "reporting_rate": 0.95,
        "reporting_chakshu_rate": 0.95,
        "reporting_cybercrime_rate": 0.95,
        "reporting_1930_rate": 0.90,
        "reporting_1930_count": 2,
        "reporting_total": 36,
        "urgent_recovery_total": 2,
        "urgent_recovery_1930": 2,
        "urgent_recovery_1930_rate": 1.0,
        "typology_total": 36,
        "typology_exact_top1_acc": 0.90,
        "typology_acceptable_top1_acc": 0.95,
        "typology_top3_acc": 0.95,
        "groundedness": 0.85,
        "language_compliance_rate": 1.0,
        "ambiguous_total": 3,
        "ambiguous_interviewed": 3,
        "median_latency_ms": 100.0,
        "p95_latency_ms": 150.0,
        "by_lang": {
            "en": {"scam_total": 20, "scam_warned": 19, "legit_total": 10, "legit_clean": 9},
            "hinglish": {"scam_total": 16, "scam_warned": 16, "legit_total": 1, "legit_clean": 1},
        },
        "cases": [],
    }

    # Case 1: No errors in either pipeline -> No warning
    md_no_err = generate_markdown_report(base_metrics, base_metrics)
    assert "Evaluation Warning" not in md_no_err

    # Case 2: Only Baseline B0 has errors
    b0_err_metrics = dict(base_metrics, eval_errors=2, evaluated_cases=48)
    md_b0_err = generate_markdown_report(b0_err_metrics, base_metrics)
    assert "Evaluation Warning" in md_b0_err
    warn_b0 = next(line for line in md_b0_err.splitlines() if line.startswith("> ⚠️"))
    assert "Baseline B0: 2 error(s) (48/50 cases evaluated)" in warn_b0
    assert "Agentic pipeline:" not in warn_b0

    # Case 3: Only Agentic has errors
    ag_err_metrics = dict(base_metrics, eval_errors=1, evaluated_cases=49)
    md_ag_err = generate_markdown_report(base_metrics, ag_err_metrics)
    assert "Evaluation Warning" in md_ag_err
    warn_ag = next(line for line in md_ag_err.splitlines() if line.startswith("> ⚠️"))
    assert "Agentic pipeline: 1 error(s) (49/50 cases evaluated)" in warn_ag
    assert "Baseline B0:" not in warn_ag

    # Case 4: Both have errors
    md_both_err = generate_markdown_report(b0_err_metrics, ag_err_metrics)
    assert "Evaluation Warning" in md_both_err
    warn_both = next(line for line in md_both_err.splitlines() if line.startswith("> ⚠️"))
    assert "Agentic pipeline: 1 error(s) (49/50 cases evaluated)" in warn_both
    assert "Baseline B0: 2 error(s) (48/50 cases evaluated)" in warn_both

