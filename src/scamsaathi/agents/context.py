"""Runtime dependencies shared by the agent nodes, and the raw-text vault.

The context is passed to nodes by closure when the graph is built. It is never part of
graph state, so nothing in it is checkpointed. The vault holds the original text and the
unmasked entities for the duration of one ``invoke`` only (ADR-007, docs/05 conventions).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from scamsaathi.config import Settings
from scamsaathi.graph.state import RoutingConfig, ScamState, load_routing_config
from scamsaathi.kb.factory import build_retriever
from scamsaathi.kb.retrieval import Retriever
from scamsaathi.kb.store import KnowledgeBase, load_kb, load_kb_config
from scamsaathi.llm import LLMGateway, LLMGatewayError, LLMResult, RequestBudget
from scamsaathi.llm.gateway import build_gateway
from scamsaathi.prompts import Prompt
from scamsaathi.tools.entities import RawEntity
from scamsaathi.tools.intel_db import IntelDB
from scamsaathi.tools.pii_masker import MaskResult
from scamsaathi.tools.risk_scorer import ScoringConfig, load_scoring_config

logger = logging.getLogger("scamsaathi.agents")

T = TypeVar("T", bound=BaseModel)


@dataclass
class RawRequest:
    """Originals for one request. In memory only; never logged or checkpointed."""

    text: str
    mask: MaskResult | None = None
    entities: list[RawEntity] = field(default_factory=list)


class RawVault:
    """Thread-safe, per-request store for originals, keyed by request ID."""

    def __init__(self) -> None:
        self._items: dict[str, RawRequest] = {}
        self._lock = threading.Lock()

    def put(self, request_id: str, item: RawRequest) -> None:
        with self._lock:
            self._items[request_id] = item

    def get(self, request_id: str) -> RawRequest | None:
        with self._lock:
            return self._items.get(request_id)

    def pop(self, request_id: str) -> None:
        with self._lock:
            self._items.pop(request_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


@dataclass
class AgentContext:
    gateway: LLMGateway
    db: IntelDB
    kb: KnowledgeBase
    retriever: Retriever
    scoring: ScoringConfig
    routing: RoutingConfig
    max_llm_calls: int
    top_k: int = 4
    vault: RawVault = field(default_factory=RawVault)

    def llm_allowance(self, state: ScamState, reserve: int = 0) -> int:
        """LLM calls this node may still make, keeping ``reserve`` for later nodes."""
        return max(0, self.max_llm_calls - state.get("llm_calls", 0) - reserve)

    def call_llm(
        self,
        state: ScamState,
        *,
        node: str,
        prompt: Prompt,
        tier: str,
        user: str,
        schema: type[T],
        reserve: int = 0,
    ) -> tuple[LLMResult[T] | None, dict[str, Any]]:
        """Call the gateway within the request budget.

        Returns the result (or None when skipped or failed) and the state update for
        ``llm_calls``, ``errors``, and ``degraded``. Never raises gateway errors: every LLM
        node has a deterministic fallback (docs/04 principle 4).
        """
        allowance = self.llm_allowance(state, reserve)
        used = state.get("llm_calls", 0)
        if allowance <= 0:
            return None, {"errors": [f"{node}: skipped, LLM call budget reached"]}
        budget = RequestBudget(max_calls=allowance)
        try:
            result = self.gateway.generate(
                task=prompt.name, tier=tier, system=prompt.text, user=user, schema=schema,
                budget=budget, prompt_version=prompt.version,
            )
        except LLMGatewayError as exc:
            logger.warning("agent_llm_failed", extra={"node": node, "error_type": type(exc).__name__})
            return None, {
                "llm_calls": used + budget.calls,
                "errors": [f"{node}: {type(exc).__name__}"],
                "degraded": True,
            }
        return result, {"llm_calls": used + budget.calls}


def build_context(
    settings: Settings,
    *,
    gateway_factory: Callable[[Settings], LLMGateway] = build_gateway,
) -> AgentContext:
    kb = load_kb()
    kb_config = load_kb_config()
    return AgentContext(
        gateway=gateway_factory(settings),
        db=IntelDB.build(),
        kb=kb,
        retriever=build_retriever(kb, kb_config, settings),
        scoring=load_scoring_config(),
        routing=load_routing_config(),
        max_llm_calls=settings.max_llm_calls_per_request,
        top_k=kb_config.top_k,
    )
