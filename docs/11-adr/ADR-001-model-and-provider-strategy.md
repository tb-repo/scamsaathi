# ADR-001: Model and provider strategy

| Field | Value |
|---|---|
| Status | Accepted. Model IDs set (ADR-008) and verified live 2026-11-13. Addendum 2026-11-13: quality first |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

- The laptop has 16 GB RAM and no GPU, so local LLM hosting is impractical for acceptable quality and speed, especially on Hinglish.
- The author purchased Gemini API access. The billing page shows Paid tier 1, a prepaid balance of Rs.500, and about Rs.6.67K of eligible promotional credits. Public forum statements from Google staff indicate eligible promotional credits are consumed before the prepaid balance; this is not yet verified on the author's account (R-004).
- Free-tier Gemini quotas reported by third parties are small and changing, so the design must not depend on them.
- Most pipeline steps are deterministic and need no LLM.

## Options considered

1. **Gemini only, single model.** Simple. Wasteful for easy steps and no resilience.
2. **Gemini tiered (fast + reasoning) with optional Groq fallback and local cache.** Cost-efficient, resilient, small added complexity.
3. **Multi-provider equal footing (OpenAI, Anthropic, Gemini).** Highest flexibility, more cost and key management, not needed.
4. **Local models via Ollama.** Rejected: hardware constraint.

## Decision

Option 2.

- Primary provider: Google Gemini API (paid tier).
- Two tiers by configuration: `fast` for intake/extraction/guardrail, `reasoning` for ambiguous classification and explanation/advice.
- Embeddings: see ADR-004.
- Optional fallback: a second provider (for example Groq free tier) for the `fast` tier only, enabled by config. Not required for MVP.
- A provider-agnostic `llm_gateway` handles retries, schema validation, caching, budgets, masking assertion, and modes (`live`, `cached`, `offline`).
- Model IDs are never hardcoded. They are set in `config/llm.yaml` after confirming availability and pricing in AI Studio.
- Only synthetic or masked data is sent to the provider.

## Consequences

Positive: low cost per request, resilience, reproducible demos, easy provider swap.
Negative: gateway adds engineering work; two model tiers need separate prompt tuning.
Follow-ups:
- Confirm model IDs, rate limits, pricing, and data-use terms (Q-3, Q-4).
- Verify credit consumption order empirically after first calls (R-004).
- Set budget alert and API key restrictions.
- Record the SDK choice (Google Gen AI SDK direct vs LangChain adapter) after the spike.

How we will know it was wrong: cost per request exceeds plan, frequent 429 errors despite paid tier, or Hinglish quality gap too large on the `fast` tier.

## Addendum (2026-11-13): quality first; budgets are safeguards

**Context.** The first live runs cost about ₹9 (mostly the 15-sample agent run: about ₹0.5 per sample, with the reasoning-tier explanation call the largest part). The author set a ₹100 monthly spend cap in AI Studio as a safety net, and directed that the app should use the LLM wherever it genuinely improves the result. Usage is not to be reduced at the expense of quality.

**Decision.**
1. **Answer quality is the objective (O-7).** An LLM step is added or kept when it measurably improves accuracy, groundedness, or language quality. It is not removed or shortened to save cost. Prompts keep their full evidence and knowledge context. Prompt changes are made for accuracy and checked against tests or evaluation.
2. **Budgets exist to stop bugs and runaway loops,** not to minimise spend. `SCAMSAATHI_MAX_LLM_CALLS_PER_REQUEST` default raised from 4 to **6**. With 4, an interview case had to skip the second classification after the user's answers (seen in tests). With 6, every step runs (extract, classify, extract, classify, explain) and one repair retry is left spare. The daily call budget (500) and the response cache stay.
3. **Optional LLM steps planned in docs/05 are enabled:** LLM-written interview questions (task 5.1, static bank as the offline fallback), and the LLM groundedness check in the guardrail (Phase 6), alongside the rule checks.
4. **Evaluation (Phase 7) runs the full dataset and all baselines.** A cost estimate is given beforehand only so the author can set the spend cap.

**Consequences.** Cost per assessment is about ₹0.5 to ₹1 in live mode and nothing on cache hits. The ₹100 cap covers development. A full evaluation may need a higher cap, which is the author's decision.

**Billing (R-004).** After the first ₹8.72 of usage, the prepaid balance still showed ₹500.00. That points to the promotional GCP credits being used first, but costs can take up to 24 hours to appear. The check is closed once the credit summary shows the promotional balance going down.

## Related
CON-2, CON-3, NFR-003 to NFR-006, FR-072 to FR-076, documents 04 and 08.
