"""A6 Risk Scoring node (FR-031 to FR-034; ADR-003). Pure code over the deterministic scorer.

Classifier confidence counts only when it came from the LLM. Retrieval-only typologies are
used for advice but add no points, so a degraded run scores exactly like baseline B0.
"""

from __future__ import annotations

from typing import Any

from scamsaathi.agents.classifier import retrieval_classification
from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState, dump, read
from scamsaathi.schemas import ClassificationResult, IntelResult, Signal
from scamsaathi.tools.risk_scorer import LLMAdjustment, Situation, score


def scoring(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    classification = read(state, "classification", ClassificationResult)
    if classification is None:  # fast path skipped the classifier
        classification = retrieval_classification(state)
    from_llm = state.get("classification_source") == "llm"
    adjustment = read(state, "llm_adjustment", LLMAdjustment) if from_llm else None

    result = score(
        [Signal.model_validate(s) for s in state.get("signals", [])],
        read(state, "intel", IntelResult) or IntelResult(),
        ctx.scoring,
        classification=classification if from_llm else None,
        situation=read(state, "situation", Situation) or Situation(),
        llm_adjustment=adjustment,
    )
    ranked = sorted(classification.matches, key=lambda m: -m.confidence)
    typologies = [m.code for m in ranked] if result.level != "LOW" else []
    return {"score": dump(result), "classification": dump(classification),
            "typologies": typologies}
