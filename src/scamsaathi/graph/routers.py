"""Routing functions (A0 Orchestrator; docs/05 routing rules, ADR-006). Pure and deterministic."""

from __future__ import annotations

from typing import Literal

from scamsaathi.graph.state import RoutingConfig, ScamState


def route_after_prescreen(state: ScamState, config: RoutingConfig) -> Literal["score", "classify"]:
    """Skip the classifier only when it cannot improve the result (see PrescreenResult)."""
    prescreen = state.get("prescreen", {})
    confident = float(prescreen.get("confidence", 0.0)) >= config.prescreen_high_confidence
    return "score" if confident and prescreen.get("skip_classifier") else "classify"


def route_after_classify(
    state: ScamState, config: RoutingConfig
) -> Literal["plan_questions", "score"]:
    classification = state.get("classification", {})
    asked = set(state.get("asked_facts", []))
    open_facts = [f for f in classification.get("missing_facts", []) if f not in asked]
    if (classification.get("needs_more_info") and open_facts
            and state.get("followups_asked", 0) < config.max_followups):
        return "plan_questions"
    return "score"


def route_after_plan(state: ScamState) -> Literal["await_answers", "score"]:
    return "await_answers" if state.get("pending_questions") else "score"


def route_after_answers(state: ScamState) -> Literal["extract", "score"]:
    return "score" if state.get("interview_skipped") else "extract"
