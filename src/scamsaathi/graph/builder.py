"""Graph builder (task 4.1; docs/04 section 4 topology).

intake -> intel -> extract -> prescreen -> (score | classify)
classify -> (plan_questions -> await_answers -> (extract | score)) | score
score -> explain_advise -> END

Threat intelligence runs before extraction (a change from the docs/04 diagram). It needs only
the entities and the original text, not the signals. Running it first lets the extractor
check its signals against the intel findings on every pass, including after interview
answers, while intel still runs exactly once, before any pause.

The guardrail node (A9) is added in Phase 6. Nodes receive the ``AgentContext`` by
closure, so runtime dependencies and originals never enter the checkpointed state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from scamsaathi.agents.classifier import classify, prescreen
from scamsaathi.agents.context import AgentContext
from scamsaathi.agents.explain_advise import explain_advise
from scamsaathi.agents.extraction import extraction
from scamsaathi.agents.intake import intake
from scamsaathi.agents.intel_node import intel
from scamsaathi.agents.interview import await_answers, plan_questions
from scamsaathi.agents.scoring import scoring
from scamsaathi.graph import routers
from scamsaathi.graph.state import ScamState

Node = Callable[[ScamState, AgentContext], dict[str, Any]]

NODES: dict[str, Node] = {
    "intake": intake,
    "extract": extraction,
    "intel": intel,
    "prescreen": prescreen,
    "classify": classify,
    "plan_questions": plan_questions,
    "await_answers": await_answers,
    "score": scoring,
    "explain_advise": explain_advise,
}


def _bind(node: Node, ctx: AgentContext) -> Any:
    """Close over the context. Returns ``Any`` because LangGraph's node protocol needs a
    parameter literally named ``state``, which a ``Callable`` type cannot express."""

    def run(state: ScamState) -> dict[str, Any]:
        return node(state, ctx)

    run.__name__ = node.__name__
    return run


def build_graph(
    ctx: AgentContext, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[Any, Any, Any, Any]:
    config = ctx.routing
    builder = StateGraph(ScamState)
    for name, node in NODES.items():
        builder.add_node(name, _bind(node, ctx))

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "intel")
    builder.add_edge("intel", "extract")
    builder.add_edge("extract", "prescreen")
    builder.add_conditional_edges(
        "prescreen", lambda s: routers.route_after_prescreen(s, config), ["score", "classify"]
    )
    builder.add_conditional_edges(
        "classify", lambda s: routers.route_after_classify(s, config), ["plan_questions", "score"]
    )
    builder.add_conditional_edges("plan_questions", routers.route_after_plan,
                                  ["await_answers", "score"])
    builder.add_conditional_edges("await_answers", routers.route_after_answers,
                                  ["extract", "score"])
    builder.add_edge("score", "explain_advise")
    builder.add_edge("explain_advise", END)
    return builder.compile(checkpointer=checkpointer)
