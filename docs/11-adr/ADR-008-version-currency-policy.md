# ADR-008: Version currency policy (runtime, libraries, AI models)

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

Runtimes, libraries, and AI models move fast. Using versions from memory risks missing security fixes, bug fixes, and capability gains, or picking deprecated models. The author asked that every choice be checked against current official sources.

## Decision

1. **Verify at decision time, from official sources.** Before choosing or changing a version, check the primary source (python.org release status, PyPI, the Gemini models, pricing, and deprecations pages). Record the source and date where the version is set.
2. **Latest stable, not preview.** Use the newest stable release. Preview, experimental, and "-latest" aliases are not used for scored runs, because they can change silently and break reproducibility.
3. **Pin what was verified.** Exact pins in `requirements.txt` and `requirements.lock`; model IDs in `config/llm.yaml`. Upgrades are deliberate commits, not side effects.
4. **Compatibility beats novelty when they conflict.** A newer version is adopted only if all dependencies ship compatible wheels and the tests pass. Example: `tenacity` is held below 9.2 because `google-genai` 3.2.0 requires `<9.2.0`.
5. **Re-check at every phase start** (added to the Definition of Done in document 10): `pip list --outdated`, a vulnerability check, and the Gemini deprecations page. Findings go in the implementation log.
6. **Automated guard:** a unit test fails if a configured model is a preview, experimental, or 1.x/2.x model.

## Verified on 2026-11-11

| Item | Chosen | Latest available | Source | Note |
|---|---|---|---|---|
| Python | 3.13.14 (installed) | 3.15 (released 2026-10-09; bugfix phase) | devguide.python.org/versions | 3.13 is now security-only. Upgrade proposed, see below |
| Direct libraries | pydantic 2.14.3, pydantic-settings 2.16.2, PyYAML 6.0.3, google-genai 3.2.0, langgraph 1.2.20, langgraph-checkpoint-sqlite 3.1.3 | Same (`pip list --outdated` shows none outdated) | PyPI | Installed unpinned, so pip resolved the latest |
| Transitive | tenacity 9.1.4, uuid_utils 0.19.0 | 9.2.1, 1.2.0 | PyPI | Held back by upstream version constraints; not under our control |
| Fast tier model | gemini-3.5-flash-lite | Stable | aistudio.google.com/docs/models | $0.30 / $2.50 per 1M tokens |
| Reasoning tier model | gemini-3.8-flash | Newest stable Flash | same | $0.75 / $3.75 until 2026-12-31, then $1.50 / $7.50 |
| Reasoning fallback | gemini-3.6-flash | Stable | same | |
| Not chosen | gemini-4-argon, gemini-4-carbon | Frontier models | same | Higher cost; reserve for an optional comparison run |
| Avoided | gemini-2.5-* | Deprecated; auto-routed to newer models from 2026-12-01 | same | |

## Python upgrade proposal

Python 3.15 is the latest stable release; 3.14 is the previous one, about a year mature. Both are in the bugfix phase, while 3.13 now receives only security fixes. Spot checks on PyPI show Python 3.15 Windows wheels for pydantic-core, orjson, ormsgpack, xxhash, cryptography, and cffi. `zstandard` and `uuid_utils` could not be confirmed. Because the device blocks native build tools, any missing wheel is a hard blocker. Plan: install 3.15, create a fresh venv with `--only-binary :all:`, run the test suite; fall back to 3.14 if any wheel is missing.

**Author decision (2026-11-11): stay on Python 3.13 for now.** 3.13 remains supported with security fixes until 2029-10, which covers the project timeline. The code targets Python 3.11+ (`requires-python`), so a later upgrade needs only a new venv and a test run. Revisit at the next phase-start version check.

## Consequences

Small recurring effort at each phase start. In return: fewer known vulnerabilities, no deprecated models in the demo, and documented evidence for evaluators.

## Related
ADR-001, ADR-002, document 10 (Definition of Done), document 12 (R-011, R-015).
