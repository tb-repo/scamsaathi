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
    assert rule_signals.detect_situation("I already paid Rs 5000")["money_sent"]
    assert rule_signals.detect_situation("I shared the OTP with him")["credentials_shared"]
    assert rule_signals.detect_situation("maine paise bhej diye")["money_sent"]
    assert not any(rule_signals.detect_situation("Got a message about my parcel").values())


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

