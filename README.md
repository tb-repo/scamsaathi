# ScamSaathi

**An agentic AI assistant that helps mobile users in India identify scams and scam attempts, explains why, and recommends safe next steps before they lose money.**

| | |
|---|---|
| Status | Phase 3 (knowledge base and retrieval) done, except the dense-embedding comparison, which needs the API key. Phases 1 and 2 done apart from the first live Gemini call and secret scan. |
| Type | Capstone project, Agentic AI certification |
| Orchestration | LangGraph (see ADR-002) |
| Primary LLM | Google Gemini API, paid tier (see ADR-001) |
| Scope (MVP) | Text-first, English and Hinglish, India-specific |

> ScamSaathi gives a **risk assessment with reasons**, not a legal or definitive verdict.

## Documentation

All project documentation lives in [`docs/`](docs/README.md). Start there.

## Repository layout (planned)

```
AgenticAI/
  README.md
  .gitignore
  .env.example
  docs/                 Project documentation (this phase)
  src/scamsaathi/       Application code (next phase)
  data/                 Synthetic datasets, knowledge base, blocklists
  tests/                Unit, integration, evaluation tests
  .kiro/specs/          Kiro spec files (requirements, design, tasks)
```

## Security note

API keys go in `.env` only. `.env` is git-ignored. Never commit keys. Use synthetic data only (see `docs/08-security-privacy-responsible-ai.md`).
