"""A3 Threat Intelligence node (task 4.3; FR-021 to FR-024).

Pure code over the local intel database. It needs the unmasked entities, so it reads them
from the vault and writes only masked findings to state. It runs once per assessment,
straight after intake and before any interview pause (docs/05 conventions), so that signal
extraction can be checked against its findings.

Parallel lookups (docs/05 A3) are not used. Every lookup is a local, in-memory SQLite
query or string check taking microseconds, so a thread pool would add overhead and no
speed. The optional external reputation API is not enabled in the MVP. If it is added,
it belongs here with a thread pool and a short timeout.
"""

from __future__ import annotations

from typing import Any

from scamsaathi.agents.context import AgentContext
from scamsaathi.graph.state import ScamState
from scamsaathi.schemas import IntelResult
from scamsaathi.tools.intel import run_intel


def intel(state: ScamState, ctx: AgentContext) -> dict[str, Any]:
    raw = ctx.vault.get(state["request_id"])
    if raw is None:
        return {"intel": IntelResult(degraded=True).model_dump(mode="json"),
                "errors": ["intel: originals not available"], "degraded": True}
    result = run_intel(raw.entities, raw.text, ctx.db)
    return {"intel": result.model_dump(mode="json")}
