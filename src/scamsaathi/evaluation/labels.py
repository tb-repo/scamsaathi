"""Outcome-based case labels and checks (docs/07 section 7.1, docs/09; decision 2026-11-13).

A risk level is ScamSaathi's own way of telling users how worried to be; it does not exist
in reality. Cases are therefore labelled with facts that do exist in reality:

- ``label``: scam, legit, or ambiguous (not enough information to tell);
- ``typologies``: acceptable scam types, if a scam;
- ``required``: behaviours that must happen whatever the score.

The core outcome follows from the label: a scam must be warned about (level above LOW), a
genuine message must not raise an alarm (LOW), and an ambiguous case must lead to questions.
Missing a scam is the worst error; a false alarm is the second (it teaches people to ignore
warnings).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from scamsaathi.schemas import AdviceBundle, IntelResult, RiskScore

Label = Literal["scam", "legit", "ambiguous"]
Behaviour = Literal[
    "report_channel",  # suspected fraud: an official reporting step in the top 3 actions
    "urgent_recovery",  # money or secrets lost: urgent mode with 1930 first
    "child_safety_path",  # minor at risk: police first, do not forward
    "spam_1909",  # promotional number or header: the 1909 route is offered
    "no_designated_label",  # a TRAI-designated number is never labelled scam or spam
    "no_questions",  # a complete pasted message must not be interviewed
]

CHAKSHU_URL = "https://sancharsaathi.gov.in/sfc"
_REPORT_TOP_N = 3


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    language: Literal["en", "hinglish", "hi"]
    label: Label
    typologies: list[str] = Field(default_factory=list)  # acceptable top typology codes
    required: list[Behaviour] = Field(default_factory=list)
    notes: str = ""


def load_cases(path: Path) -> list[Case]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Case.model_validate(json.loads(line)) for line in lines if line.strip()]


def check_core(case: Case, risk: RiskScore, asked_questions: bool | None) -> list[str]:
    """The outcome implied by the label. ``asked_questions`` is None for B0 (no interview)."""
    failures: list[str] = []
    if case.label == "scam" and risk.level == "LOW":
        failures.append("missed scam: level is LOW")
    if case.label == "legit" and risk.level != "LOW":
        failures.append(f"false alarm: level is {risk.level}")
    if case.label == "ambiguous" and asked_questions is False:
        failures.append("ambiguous case was not interviewed")
    return failures


def check_behaviours(case: Case, risk: RiskScore, advice: AdviceBundle | None,
                     intel: IntelResult | None, asked_questions: bool | None) -> list[str]:
    failures: list[str] = []
    actions = advice.actions if advice else []
    values = [c.value for c in advice.contacts] if advice else []
    for behaviour in case.required:
        if behaviour == "report_channel" and advice is not None:
            top = [a.text for a in actions if a.priority <= _REPORT_TOP_N]
            if not any(CHAKSHU_URL in t for t in top):
                failures.append("no official reporting step in the top 3 actions")
        elif behaviour == "urgent_recovery":
            if "urgent_recovery" not in risk.overrides:
                failures.append("urgent recovery not triggered")
            elif advice is not None and not (advice.urgent_recovery_mode
                                              and actions and "1930" in actions[0].text):
                failures.append("1930 is not the first action")
        elif behaviour == "child_safety_path":
            if "child_safety" not in risk.overrides:
                failures.append("child-safety path not triggered")
            elif advice is not None and not (actions and "police" in actions[0].text.lower()):
                failures.append("police is not the first action")
        elif behaviour == "spam_1909" and advice is not None:
            if "1909" not in values:
                failures.append("1909 route not offered")
        elif behaviour == "no_designated_label" and intel is not None:
            for f in intel.findings:
                # The blocklist itself cannot hold designated numbers (IntelDB.build refuses).
                if f.check == "designated_series" and (f.severity != "info"
                                                        or "spam" in f.detail.lower()):
                    failures.append("designated-series number was labelled")
        elif behaviour == "no_questions" and asked_questions:
            failures.append("asked questions about a complete message")
    return failures


def check_typology(case: Case, typologies: list[str]) -> list[str]:
    if case.label != "scam" or not case.typologies:
        return []
    top = typologies[0] if typologies else None
    if top not in case.typologies:
        return [f"top typology {top} not in {case.typologies}"]
    return []
