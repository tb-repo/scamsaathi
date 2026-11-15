# 11. Architecture Decision Records

ADRs capture significant decisions with context, options, and consequences. They are append-only: a changed decision gets a new ADR that supersedes the old one.

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-000](ADR-000-template.md) | Template | n/a | 2026-11-11 |
| [ADR-001](ADR-001-model-and-provider-strategy.md) | Model and provider strategy | Accepted (model IDs set via ADR-008, verified live 2026-11-13) | 2026-11-11 |
| [ADR-002](ADR-002-orchestration-framework.md) | Orchestration framework: LangGraph | Accepted (spike passed, task 1.11) | 2026-11-11 |
| [ADR-003](ADR-003-hybrid-risk-scoring.md) | Hybrid deterministic risk scoring | Accepted | 2026-11-11 |
| [ADR-004](ADR-004-vector-store-and-embeddings.md) | Retrieval: hybrid BM25 + Gemini embeddings, no vector DB | Accepted (revised; dense comparison done 2026-11-13) | 2026-11-11 |
| [ADR-005](ADR-005-api-and-ui.md) | API and UI technology | Accepted (FastAPI + Streamlit implemented in Phase 5 / Phase 8) | 2026-11-11 |
| [ADR-006](ADR-006-orchestrator-as-graph.md) | Orchestrator is the graph, not an LLM | Accepted | 2026-11-11 |
| [ADR-007](ADR-007-data-handling-and-privacy.md) | Data handling and privacy policy | Accepted | 2026-11-11 |
| [ADR-008](ADR-008-version-currency-policy.md) | Version currency policy (runtime, libraries, models) | Accepted | 2026-11-11 |
| [ADR-009](ADR-009-regulatory-compliance-posture.md) | Regulatory compliance posture (paste-only, designated number series, no legal advice) | Accepted | 2026-11-12 |

Statuses: Proposed, Accepted, Deprecated, Superseded.
