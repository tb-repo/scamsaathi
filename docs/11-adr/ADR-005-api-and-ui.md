# ADR-005: API and UI technology

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

Need a mobile-friendly UI for demos, a clean API for tests and extensibility, and minimal frontend effort.

## Options

UI: Streamlit, Gradio, or a small custom HTML/JS page served by FastAPI.
API: FastAPI (typed, OpenAPI docs, async).

| Criterion | Streamlit | Gradio | Custom HTML + FastAPI |
|---|---|---|---|
| Speed to build | High | High | Medium |
| Chat-style follow-up flow | Good (chat elements) | Good | Full control |
| Mobile layout control | Medium | Medium | High |
| Accessibility control | Medium | Medium | High |
| Extra dependencies | Streamlit | Gradio | None |

## Decision (proposed)

FastAPI for the API (certain). For the UI, start with Streamlit calling the API, because the interview flow maps well to chat elements and it is fast to build. Revisit if mobile layout or accessibility checks fail (NFR-011, NFR-012); a custom page is the fallback.

## Consequences

UI stays a thin client over the API, so it can be replaced without touching the agents.

## Related
FR-070, FR-071, NFR-011, NFR-012.
