"""UT-SCORE-01..13 (FR-031 to FR-034, NFR-007, ADR-003)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scamsaathi.schemas import (
    ClassificationResult,
    IntelFinding,
    IntelResult,
    Severity,
    Signal,
    SignalName,
    TypologyMatch,
)
from scamsaathi.tools.risk_scorer import (
    LLMAdjustment,
    ScoringConfig,
    Situation,
    level_for,
    load_scoring_config,
    score,
)

CFG = load_scoring_config()
NO_INTEL = IntelResult()


def sig(name: SignalName, confidence: float = 1.0, eid: str = "S1") -> Signal:
    return Signal(name=name, confidence=confidence, evidence_span="x", evidence_id=eid)


def finding(check: str, severity: Severity, eid: str = "I1") -> IntelFinding:
    return IntelFinding(entity_ref="E1", check=check, severity=severity, detail="d", evidence_id=eid)


def test_ut_score_01_no_evidence_is_low_zero() -> None:
    result = score([], NO_INTEL, CFG)
    assert (result.value, result.level, result.contributions) == (0, "LOW", [])


def test_ut_score_02_weight_times_confidence() -> None:
    result = score([sig(SignalName.CREDENTIAL_REQUEST, 0.7)], NO_INTEL, CFG)
    assert result.value == 18  # 25 x 0.7 = 17.5, rounded
    assert result.contributions[0].evidence_ids == ["S1"]


def test_ut_score_03_each_signal_type_counts_once() -> None:
    twice = [sig(SignalName.URGENCY, 0.5, "S1"), sig(SignalName.URGENCY, 1.0, "S2")]
    result = score(twice, NO_INTEL, CFG)
    assert result.value == 10 and result.contributions[0].evidence_ids == ["S2"]


def test_ut_score_04_signal_cap() -> None:
    every = [sig(name, 1.0, f"S{i}") for i, name in enumerate(SignalName, start=1)]
    signal_only = score(every, NO_INTEL, CFG.model_copy(update={"combos": []}))
    assert signal_only.value == CFG.signal_cap


def test_ut_score_05_combo_adds_points() -> None:
    pair = [sig(SignalName.AUTHORITY_IMPERSONATION, 1.0, "S1"), sig(SignalName.THREAT, 1.0, "S2")]
    result = score(pair, NO_INTEL, CFG)
    assert result.value == 15 + 15 + 10
    combo = next(c for c in result.contributions if c.factor.startswith("combo:"))
    assert combo.evidence_ids == ["S1", "S2"]


def test_ut_score_06_combo_cap() -> None:
    names = [SignalName.CREDENTIAL_REQUEST, SignalName.URGENCY, SignalName.LINK_PRESENT,
             SignalName.APP_INSTALL_REQUEST]  # triggers three combos worth 30
    result = score([sig(n, 0.1, f"S{i}") for i, n in enumerate(names)], NO_INTEL, CFG)
    signal_points = (25 + 10 + 5 + 20) * 0.1
    assert result.value == round(signal_points + CFG.combo_cap)


def test_ut_score_07_intel_points_capped() -> None:
    intel = IntelResult(findings=[finding(f"c{i}", "high", f"I{i}") for i in range(5)])
    assert score([], intel, CFG).value == CFG.intel_cap


def test_ut_score_08_mitigation_reduces_but_not_below_zero() -> None:
    intel = IntelResult(findings=[finding("official_domain", "info")])
    assert score([sig(SignalName.LINK_PRESENT, 1.0)], intel, CFG).value == 0
    some = [sig(SignalName.PAYMENT_REQUEST, 1.0)]
    assert score(some, intel, CFG).value == 20 - 10


def test_ut_score_09_blocklist_floor() -> None:
    intel = IntelResult(findings=[finding("blocklist", "high")])
    result = score([], intel, CFG)
    assert result.level == "HIGH" and "blocklist_floor" in result.overrides


def test_ut_score_10_money_sent_floor_and_urgent_recovery() -> None:
    result = score([], NO_INTEL, CFG, situation=Situation(money_sent=True))
    assert result.value == 60 and result.level == "HIGH"
    assert "urgent_recovery" in result.overrides


@pytest.mark.parametrize(
    ("value", "level"),
    [(0, "LOW"), (29, "LOW"), (30, "MEDIUM"), (59, "MEDIUM"), (60, "HIGH"), (84, "HIGH"),
     (85, "CRITICAL"), (100, "CRITICAL")],
)
def test_ut_score_11_threshold_boundaries(value: int, level: str) -> None:
    assert level_for(value, CFG) == level


def test_ut_score_12_deterministic_and_order_independent() -> None:
    signals = [sig(SignalName.THREAT, 0.7, "S1"), sig(SignalName.URGENCY, 0.7, "S2")]
    intel = IntelResult(findings=[finding("shortener", "medium")])
    classification = ClassificationResult(
        matches=[TypologyMatch(code="SC-02", confidence=0.8, supporting_evidence_ids=["S1"])]
    )
    first = score(signals, intel, CFG, classification)
    assert first == score(list(reversed(signals)), intel, CFG, classification)
    assert first.value == round(0.7 * 15 + 0.7 * 10 + 8 + 0.8 * 15)


def test_ut_score_13_bounded_llm_adjustment_respects_floor() -> None:
    up = score([sig(SignalName.URGENCY, 1.0)], NO_INTEL, CFG,
               llm_adjustment=LLMAdjustment(points=50, reason="clear scam script"))
    assert up.value == 10 + 10 and up.llm_adjustment == 10
    assert up.llm_adjustment_reason == "clear scam script"

    floored = score([], IntelResult(findings=[finding("blocklist", "high")]), CFG,
                    llm_adjustment=LLMAdjustment(points=-10, reason="looks fine"))
    assert floored.value == 60 and floored.llm_adjustment == 0
    assert floored.llm_adjustment_reason is None


def test_invalid_thresholds_rejected() -> None:
    data = CFG.model_dump()
    data["thresholds"] = {"MEDIUM": 70, "HIGH": 60, "CRITICAL": 85}
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(data)
