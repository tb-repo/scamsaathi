# Changelog

Format based on Keep a Changelog. Versions follow SemVer once code exists.

## [Unreleased]

### Added
- Legal-text tooling (`scripts/extract_legal_texts.py`, `scripts/find_in_acts.py`, pypdf 7.0.1 dev dependency) and doc 16 section 10 (provisions verified from the official Acts).
- Typologies SC-13 (online money gaming), SC-14 (sextortion), SC-15 (money mule); internal `legal_refs` on all typologies; 11 Act sources.
- Signals `sextortion_threat`, `money_mule_request`, `money_game`; child-safety path; evidence and police-reporting advice; scoring config v2.
- International-number masking and flags; TRAI-designated series handling (FR-081); sender-format findings (FR-082). 177 tests.

- Official websites review (doc 16 section 11): contacts for Chakshu spam reporting, Report International Call, and Know Mobile Connections in Your Name; 30-day Chakshu reporting advice; spam routing for 140-series numbers (FR-085). 182 tests.

- Phase 4 agent graph (tasks 4.1 to 4.5):
  - LangGraph workflow with intake, intel, extraction, pre-screen, classifier (RAG), interview (static questions with `interrupt()`), scoring, and combined explanation and advice.
  - Versioned prompts, `config/routing.yaml`, `AgentRunner`, and `scripts/run_agentic.py`.
  - Masked-only state with a per-request vault for originals.
  - Validated LLM outputs, and deterministic fallbacks with exact B0 parity when the LLM is down.
  - Tests in `tests/unit/test_agent_graph.py`.
- Task 3.3: hybrid retrieval confirmed (recall@1 97% against 90% lexical); ADR-004 final.
- ADR-001 addendum: quality first; per-request LLM cap default 4 to 6.
- Reporting to the authorities is now the second step for suspected fraud, with Chakshu and the Cyber Crime Portal suspect page inline. Reworded advice must keep every link and number.
- Classifier runs for every scam case (skipped only for verified genuine messages and child safety).
- Outcome-based case labels (`evaluation/labels.py`): scam / legit / ambiguous, typologies, and required behaviours replace expected risk levels in the demo set, tests, scripts, and docs 07 and 09.
- `scripts/live_smoke.py`: first live Gemini run (task 1.10) PASSED. It checks model availability, makes one call per tier, confirms a cache hit, and calls the fallback model.
- Kiro steering file `AgenticAI/.kiro/steering/official-sources.md` (workspace root): maps every official PDF and website to its use, and sets the rules for using them during development. Loads automatically when KB, advice, contacts, intel, agent or prompt files, doc 16, or ADR-009 are in context. Runtime agents do not use it.
- TCCCPR Third Amendment 2026 Gazette text reviewed (doc 16 section 13); ADR-009 addendum 7; source `LAW_TCCCPR_2026`.

### Fixed (TRAI Gazette review)
- The 1601-series finding wrongly described it as the RBI/SEBI/IRDAI/PFRDA series; it is now the utilities, logistics and courier series (Direction of 10 Aug 2026).
- Spam advice implied every 140-series call is spam; 140xx calls are allowed until the user opts out, so complaints are advised only after opting out. Advice now asks for the sender's number or SMS header.

### Added (TRAI sources)
- TRAI sources review (doc 16 section 12): verified 1909 contact (`ucc_1909`) and 7-day UCC complaint advice; `sender_header` entity and information finding for -P/-S/-T/-G headers (FR-086); FR-087 (no in-app spam reporting); ADR-009 addendum; R-017 closed. 195 tests.

### Fixed
- International numbers were labelled as ID or account numbers, and bracketed numbers were not masked at all.
- Reward rule missed amounts with more than one digit ("Earn Rs 2000").

### Added (earlier)
- Document 16 (legal and regulatory reference), ADR-009 (compliance posture), requirements FR-080 to FR-085, risks R-017 to R-019, questions Q-9 to Q-11.
- Phase 3 knowledge base: 12 scam typologies with a source register, verified contacts, advice templates, strict KB loader, hybrid retrieval (BM25 + optional Gemini embeddings, RRF), deterministic advice builder, `scripts/build_kb.py` and `scripts/eval_retrieval.py`. 134 tests.

### Changed
- ADR-004 revised: no vector database; hybrid lexical + dense retrieval.
- Credential-request negation window widened (3 to 6 words).

### Added (Phase 2)
- Phase 2 deterministic core: entity extractor, language detector, intel DB with verified official domains (incl. `.bank.in`), URL analyzer, claim-vs-link checks, rule-based signals (English + Hinglish), deterministic risk scorer with `config/scoring.yaml`, rules-only baseline B0 and `scripts/run_baseline.py`. 115 tests.

### Fixed
- Query strings now removed from bare links (e.g. `wa.me/...?x=`) before masking.
- Entity placeholders now match message-level placeholders.

### Added (earlier)
- ADR-008 version currency policy; verified model IDs in `config/llm.yaml` (gemini-3.5-flash-lite, gemini-3.8-flash, fallback gemini-3.6-flash); guard test against preview or deprecated models.
- Phase 1 foundations: project scaffold, pinned dependencies, settings loader, shared schemas, PII masker, PII-safe JSON logging, LLM gateway (Gemini provider, disk cache, live/cached/offline modes, per-request and daily budgets, retries, fallback chain, schema repair), and 32 unit tests.
- Issues I-002 (ruff blocked) and I-003 (venv in OneDrive); I-001 closed.
- Kiro spec files `.kiro/specs/scamsaathi-mvp/` (requirements, design, tasks).
- Issue I-001 (Python not installed) in the risk and issues log.
- Objective O-7 (quality and accuracy), success criterion SC-3a, and NFR-018 to NFR-020.
- ADR-004: rationale for not using an external/managed vector database.
- Documentation set 01 to 15 (v0.1 drafts).
- ADR-001 to ADR-007.
- Repository scaffolding files: `README.md`, `.gitignore`, `.env.example`.

## [0.1.0-docs] - 2026-11-11

### Added
- Initial documentation baseline for ScamSaathi.
