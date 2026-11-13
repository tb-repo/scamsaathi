# ADR-006: The orchestrator is the graph, not an LLM

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

An early idea was an LLM "supervisor agent" that decides which agent runs next. Routing here is based on measurable quantities (confidence, missing facts, counters, budget).

## Options

1. LLM supervisor decides routing each step. Flexible, adds calls, latency, cost, and nondeterminism.
2. Graph with deterministic routing functions driven by state values.

## Decision

Option 2. The Orchestrator (A0) is the LangGraph state machine and its routers. LLM calls are made only inside task nodes.

## Consequences

Positive: lower cost and latency, reproducible routing, easier tests.
Negative: less adaptive to unforeseen cases. Mitigation: router thresholds are configurable, and an LLM-routed variant can be an optional experiment for the report.
For the certification narrative: the system is still multi-agent (specialised, cooperating nodes with tools, memory, and loops); orchestration is explicit rather than learned.

## Related
Document 05 (A0), ADR-002, ADR-003.
