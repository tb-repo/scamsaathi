# ADR-002: Orchestration framework

| Field | Value |
|---|---|
| Status | Accepted. Spike passed 2026-11-11; course requirement unconfirmed (Q-1) |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

The workflow has a defined shape with conditional routing (fast path vs reasoning path), a loop (interview), human-in-the-loop pause/resume, mixed LLM and deterministic nodes, and a retry loop after guardrail failure.

## Options considered and weighted comparison

Scores are the author's judgement from general knowledge (1 to 5), pending the spike. Framework features and versions have not been re-verified for this ADR.

| Criterion | Weight | LangGraph | CrewAI | AutoGen/AG2 | Google ADK | Plain Python |
|---|---|---|---|---|---|---|
| Control flow and branching | 5 | 5 | 3 | 3 | 4 | 5 |
| State and checkpoint / resume | 5 | 5 | 3 | 3 | 4 | 2 |
| Mix of LLM and code nodes | 4 | 5 | 3 | 3 | 4 | 5 |
| Testability of single nodes | 4 | 5 | 3 | 3 | 4 | 5 |
| Provider flexibility | 3 | 4 | 4 | 4 | 3 | 5 |
| Observability / tracing | 3 | 5 | 3 | 3 | 4 | 2 |
| Learning curve and speed | 3 | 3 | 5 | 3 | 3 | 4 |
| Community, docs, maturity | 3 | 5 | 4 | 4 | 3 | 5 |
| Certification recognisability | 2 | 5 | 5 | 4 | 3 | 1 |
| **Weighted total** (sum of weight x score) | | **see below** | | | | |

Weighted totals (max 160): LangGraph 5x5+5x5+4x5+4x5+3x4+3x5+3x3+3x5+2x5 = 25+25+20+20+12+15+9+15+10 = **151**. CrewAI 15+15+12+12+12+9+15+12+10 = **112**. AutoGen/AG2 15+15+12+12+12+9+9+12+8 = **104**. Google ADK 20+20+16+16+9+12+9+9+6 = **117**. Plain Python 25+10+20+20+15+6+12+15+2 = **125**.

## Decision

Use **LangGraph** with Pydantic-typed state and a SQLite checkpointer. Keep nodes as plain functions so they remain testable and could be ported.

## Validation plan (time-boxed spike, about half a day, in P1)

Implement a 4-node mini graph (extract, branch on confidence, interview loop with pause/resume, score) in LangGraph. Compare briefly with a plain-Python version. Record code size, clarity, debugging experience in the implementation log. If LangGraph fails the spike, supersede this ADR.

## Spike result (2026-11-11, langgraph 1.2.20, langgraph-checkpoint-sqlite 3.1.3, Python 3.13, Windows)

Implemented in `tests/spike/test_langgraph_spike.py` (4 tests, all passing):

| Capability needed | Result |
|---|---|
| Conditional routing on confidence | Works: `add_conditional_edges` with a plain router function; graph wiring is about 10 lines |
| Interview loop (interview back to extract) | Works, including a hard follow-up cap |
| Pause for user input | `interrupt(payload)` inside the node; questions read from `get_state(config).interrupts` |
| Resume after a process restart | Works: a new `SqliteSaver` and a new compiled graph on the same DB file resumed with `Command(resume=answer)` |
| Only masked text persisted | Verified by scanning every row of the checkpoint DB: placeholder present, raw phone and UPI absent |

Findings that become design rules (added to document 05 conventions):
1. **A node re-runs from the top on resume.** Code before `interrupt()` must be side-effect free (no LLM calls, no writes), or it will repeat and cost money.
2. **Checkpoints store state verbatim.** The reversible PII map must never be placed in graph state or in `configurable`; it stays in request memory only. Intel lookups that need original values run before any interrupt, and only their masked findings enter state.

Not done: a parallel plain-Python implementation. The spike showed that the hardest part to hand-write, durable pause and resume across restarts, is built in, so the decision stands. The ADR status is confirmed.

## Consequences

Positive: explicit, auditable workflow; native pause/resume; Mermaid export for documentation.
Negative: framework learning curve; API changes between versions (pin versions).
Risk: if the certification requires another framework, this must be revisited (Q-1).

## Related
Document 04 and 05, ADR-006.
