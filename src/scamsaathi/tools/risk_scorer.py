"""Deterministic risk scorer (task 2.6; FR-031 to FR-034; ADR-003).

A pure function: identical inputs always give identical outputs (NFR-007). The LLM may
nudge the score within a bounded range with a logged reason, but never below a safety
floor and never by changing the level directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from scamsaathi.config import CONFIG_DIR, load_yaml
from scamsaathi.schemas import (
    ClassificationResult,
    Contribution,
    IntelResult,
    RiskLevel,
    RiskScore,
    Signal,
)


class Combo(BaseModel):
    name: str
    signals: list[str] = Field(min_length=2)
    points: float = Field(ge=0)


class Overrides(BaseModel):
    blocklist_floor: int = Field(ge=0, le=100)
    money_or_credentials_lost_floor: int = Field(ge=0, le=100)
    child_safety_floor: int = Field(ge=0, le=100)


class ScoringConfig(BaseModel):
    version: int
    thresholds: dict[str, int]
    signal_weights: dict[str, float]
    signal_cap: float
    intel_points: dict[str, float]
    intel_cap: float
    combos: list[Combo]
    combo_cap: float
    classification_weight: float
    mitigations: dict[str, float]
    mitigation_cap: float
    overrides: Overrides
    llm_adjustment_limit: int = Field(ge=0, le=10)

    @model_validator(mode="after")
    def _check_thresholds(self) -> ScoringConfig:
        t = self.thresholds
        if not 0 < t["MEDIUM"] < t["HIGH"] < t["CRITICAL"] <= 100:
            raise ValueError("thresholds must satisfy 0 < MEDIUM < HIGH < CRITICAL <= 100")
        return self


FactState = Literal["confirmed", "denied", "unknown"]
ActorType = Literal["user", "third_party", "unknown"]
TargetEntity = Literal["user_account", "user_device", "third_party_account", "third_party_device", "unknown"]


class ExposureFact(BaseModel):
    status: FactState = "unknown"
    actor: ActorType = "unknown"
    target: TargetEntity = "unknown"
    authorized: FactState = "unknown"
    evidence: str | None = None


class Situation(BaseModel):
    """Facts reported by the user (with explicit confirmation state)."""

    money_sent: bool = False
    credentials_shared: bool = False
    link_clicked: bool = False
    app_installed: bool = False
    child_involved: bool = False  # child-safety path (docs/16 section 10)

    # Decision-relevant structured facts:
    credentials_exposure: ExposureFact = Field(default_factory=ExposureFact)
    app_installation: ExposureFact = Field(default_factory=ExposureFact)
    money_loss: ExposureFact = Field(default_factory=ExposureFact)
    unresolved_uncertainties: list[str] = Field(default_factory=list)


class LLMAdjustment(BaseModel):
    points: int
    reason: str = Field(min_length=3)


@lru_cache(maxsize=4)
def load_scoring_config(path: Path = CONFIG_DIR / "scoring.yaml") -> ScoringConfig:
    return ScoringConfig.model_validate(load_yaml(path))


def level_for(value: int, config: ScoringConfig) -> RiskLevel:
    t = config.thresholds
    if value >= t["CRITICAL"]:
        return "CRITICAL"
    if value >= t["HIGH"]:
        return "HIGH"
    if value >= t["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def score(
    signals: list[Signal],
    intel: IntelResult,
    config: ScoringConfig,
    classification: ClassificationResult | None = None,
    situation: Situation | None = None,
    llm_adjustment: LLMAdjustment | None = None,
) -> RiskScore:
    situation = situation or Situation()
    contributions: list[Contribution] = []

    # 1. Behavioural signals: strongest instance of each type, capped.
    best: dict[str, Signal] = {}
    for signal in signals:
        current = best.get(signal.name.value)
        if current is None or signal.confidence > current.confidence:
            best[signal.name.value] = signal
    signal_points = 0.0
    for name in sorted(best):
        points = config.signal_weights.get(name, 0.0) * best[name].confidence
        if points:
            contributions.append(
                Contribution(factor=f"signal:{name}", points=round(points, 2),
                             evidence_ids=[best[name].evidence_id])
            )
            signal_points += points
    signal_points = min(signal_points, config.signal_cap)

    # 2. Combinations of signals.
    combo_points = 0.0
    for combo in config.combos:
        if all(s in best for s in combo.signals):
            contributions.append(
                Contribution(factor=f"combo:{combo.name}", points=combo.points,
                             evidence_ids=[best[s].evidence_id for s in combo.signals])
            )
            combo_points += combo.points
    combo_points = min(combo_points, config.combo_cap)

    # 3. Intelligence findings (non-mitigating), capped.
    intel_points = 0.0
    for finding in intel.findings:
        if finding.check in config.mitigations:
            continue
        points = config.intel_points.get(finding.severity, 0.0)
        if points:
            contributions.append(
                Contribution(factor=f"intel:{finding.check}", points=points,
                             evidence_ids=[finding.evidence_id])
            )
            intel_points += points
    intel_points = min(intel_points, config.intel_cap)

    # 4. Classifier confidence (bounded influence, ADR-003).
    class_points = 0.0
    if classification and classification.matches:
        top = max(classification.matches, key=lambda m: m.confidence)
        class_points = round(top.confidence * config.classification_weight, 2)
        contributions.append(
            Contribution(factor=f"classification:{top.code}", points=class_points,
                         evidence_ids=top.supporting_evidence_ids)
        )

    # 5. Mitigations (evidence of legitimacy), capped.
    mitigation = 0.0
    for finding in intel.findings:
        reduction = config.mitigations.get(finding.check)
        if reduction:
            contributions.append(
                Contribution(factor=f"mitigation:{finding.check}", points=-reduction,
                             evidence_ids=[finding.evidence_id])
            )
            mitigation += reduction
    mitigation = min(mitigation, config.mitigation_cap)

    raw = signal_points + combo_points + intel_points + class_points - mitigation
    value = int(round(max(0.0, min(100.0, raw))))

    # 6. Safety floors.
    overrides: list[str] = []
    floor = 0
    if any(f.check == "blocklist" and f.severity == "high" for f in intel.findings):
        floor = max(floor, config.overrides.blocklist_floor)
        overrides.append("blocklist_floor")
    if situation.money_sent or situation.credentials_shared:
        floor = max(floor, config.overrides.money_or_credentials_lost_floor)
        overrides.append("urgent_recovery")
    if situation.child_involved:
        floor = max(floor, config.overrides.child_safety_floor)
        overrides.append("child_safety")
    value = max(value, floor)

    # 7. Bounded LLM adjustment; cannot cross the floor (FR-034).
    adjustment = 0
    reason: str | None = None
    if llm_adjustment is not None and llm_adjustment.points:
        limit = config.llm_adjustment_limit
        adjustment = max(-limit, min(limit, llm_adjustment.points))
        adjusted = max(floor, min(100, value + adjustment))
        adjustment = adjusted - value
        value = adjusted
        reason = llm_adjustment.reason

    return RiskScore(
        value=value,
        level=level_for(value, config),
        contributions=contributions,
        overrides=overrides,
        llm_adjustment=adjustment,
        llm_adjustment_reason=reason if adjustment else None,
    )
