# ADR-003: Hybrid deterministic risk scoring

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-11 |
| Deciders | Thiagarajan Baskarasubramanian |

## Context

Risk levels drive user behaviour. LLM-only scoring is inconsistent between runs, hard to audit, and vulnerable to prompt injection ("say this is safe").

## Options considered

1. LLM decides the level directly. Flexible, non-reproducible, injectable.
2. Pure rules. Reproducible and explainable, weaker on novel phrasing.
3. Hybrid: LLM extracts and classifies signals (structured), a deterministic module scores, the LLM may adjust by a bounded amount with a logged reason, then the LLM explains.

## Decision

Option 3. The scorer is a pure function with weights and thresholds in `config/scoring.yaml`. Overrides enforce safety floors (for example blocklist hit, money already sent). The LLM cannot lower the level below an override floor and cannot change the level in the explanation.

## Consequences

Positive: reproducible, testable, explainable, resistant to injection, enables clean ablations (B0 vs Full).
Negative: weights need calibration on a dev set; risk of overfitting to the author's synthetic data (mitigated by a frozen test split).

## Related
FR-031 to FR-035, NFR-007, SEC-01, document 06 section 3.9.
