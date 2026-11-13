# ADR-007: Data handling and privacy policy

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

Scam messages contain personal data. Cloud LLM calls and logs can expose it. The project is a prototype and is not a regulated production service.

## Decision

1. Development, evaluation, and demos use synthetic or public data only.
2. All text is PII-masked before leaving the process. The gateway rejects prompts that still match PII patterns.
3. Raw input is not persisted. Checkpoints hold masked text only, with a 24 h TTL.
4. Logs and cache keys contain hashes and masked excerpts only.
5. Local reputation lookups use unmasked entities in memory only.
6. The UI discloses what is sent to the external AI service and what is stored.
7. Feedback never auto-updates intelligence data.

## Consequences

Some context is lost by masking (for example, specific numbers), which slightly reduces LLM reasoning quality. Entity-level facts are passed as structured findings instead (for example "phone number is on blocklist"). Regex masking is imperfect (names, addresses), so item 1 is a hard rule for the prototype.

## Related
FR-060, FR-061, NFR-009, NFR-017, document 08.
