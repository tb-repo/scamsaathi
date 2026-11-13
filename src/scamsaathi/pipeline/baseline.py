"""Rules-only baseline B0 (task 2.7; docs/09 section 6).

No LLM: mask -> language -> entities -> rule signals -> intel -> deterministic score.
Serves three roles: the B0 evaluation baseline, the degraded-mode fallback when the LLM
is unavailable (NFR-005), and the pre-screen input for the agent graph (Phase 4).
"""

from __future__ import annotations

from dataclasses import dataclass

from scamsaathi.schemas import Entity, IntelResult, RiskScore, Signal
from scamsaathi.tools import rule_signals
from scamsaathi.tools.entities import extract
from scamsaathi.tools.intel import run_intel
from scamsaathi.tools.intel_db import IntelDB
from scamsaathi.tools.language import LanguageResult, detect
from scamsaathi.tools.pii_masker import mask
from scamsaathi.tools.risk_scorer import ScoringConfig, Situation, load_scoring_config, score


@dataclass(frozen=True)
class BaselineResult:
    """Everything here is masked or derived; safe to log, persist, or show."""

    masked_text: str
    language: LanguageResult
    entities: list[Entity]
    signals: list[Signal]
    intel: IntelResult
    situation: Situation
    risk: RiskScore


def assess(text: str, db: IntelDB, config: ScoringConfig | None = None) -> BaselineResult:
    masked = mask(text)
    raw_entities = extract(text, masked)  # originals stay in this function's scope
    signals = rule_signals.detect(
        masked.masked_text, has_link=any(e.kind == "url" for e in raw_entities)
    )
    intel = run_intel(raw_entities, text, db)
    situation = Situation(**rule_signals.detect_situation(masked.masked_text))
    risk = score(signals, intel, config or load_scoring_config(), situation=situation)
    return BaselineResult(
        masked_text=masked.masked_text,
        language=detect(text),
        entities=[e.to_state() for e in raw_entities],
        signals=signals,
        intel=intel,
        situation=situation,
        risk=risk,
    )
