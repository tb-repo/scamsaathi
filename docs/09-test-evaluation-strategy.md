# 09. Test and Evaluation Strategy

| Field | Value |
|---|---|
| Version | 1.0 (Approved) |
| Date | 2026-11-11 |

## 1. Objectives

1. Show the system works as specified (verification).
2. Show it is useful and safe on realistic inputs (validation).
3. Provide reproducible numbers for the final report.

## 2. Test levels

| Level | ID prefix | Scope | LLM used? | Tooling |
|---|---|---|---|---|
| Unit | UT- | Deterministic tools (masker, extractor, URL analyzer, scorer, gateway logic) | No | pytest |
| Component | CT- | Individual agent nodes with a fake LLM returning canned outputs | Fake | pytest |
| Integration | IT- | Full graph with fake or cached LLM; API endpoints | Fake / cache | pytest, FastAPI TestClient |
| Evaluation | EV- | Labelled dataset through the real pipeline | Real, then cached | Evaluation script |
| Security | SEC- | Injection, PII leakage, secret scan, banned output | Mixed | pytest, scanners |
| Performance and cost | PERF- | Latency and call counts | Real | Script |
| Manual / usability | MR- | UI on mobile width, language and wording review | Real | Checklist |

## 3. Test design highlights

### 3.1 Unit tests (examples)

| ID | Subject | Case |
|---|---|---|
| UT-PII-01..10 | pii_masker | +91 numbers, spaced digits, 12-digit Aadhaar, PAN, UPI, email, amount not masked, overlapping patterns, empty text, Unicode |
| UT-ENT-01..08 | entity_extractor | URL with/without scheme, shortener, Indian phone forms, UPI IDs, amounts with symbols and words |
| UT-URL-01..10 | url_analyzer | Lookalike (character swap), brand in subdomain, IP host, punycode, `@` trick, legit official domain, HTTP login |
| UT-REP-01..05 | reputation_lookup | Blocklist hit, allowlist hit, normalisation, unknown, mixed |
| UT-SCORE-01..13 | risk_scorer | Each weight, caps, combos, override floors, determinism, boundary thresholds, bounded LLM adjustment, no-signal LOW |
| UT-LLM-01..08 | llm_gateway | Cache hit/miss, retry on 429, fallback provider, budget exceeded, schema repair, PII-in-prompt rejection, offline mode, key never logged |
| UT-API-01..04 | API validation | Empty, oversized, bad JSON, valid |
| UT-SESS-01 | sessions | Random IDs, TTL cleanup |

### 3.2 Component and integration tests

| ID | Scenario | Expected |
|---|---|---|
| IT-SIG-01 | OTP + bank impersonation message | Signals include credential_request and authority_impersonation |
| IT-RAG-01 | KYC phishing | Retrieved chunks include SC-02 |
| IT-INT-01 | Vague parcel call | needs_followup with at most 3 questions |
| IT-INT-02 | Answers provided | Workflow resumes and completes |
| IT-INT-03 | Skip | Best-effort result with uncertainty |
| IT-INT-04 | Follow-up cap | Never exceeds max follow-ups |
| IT-ADV-01..05 | Advice | Correct contacts; recovery mode when money sent |
| IT-API-01 | End-to-end API | 200 with valid schema |
| IT-DEG-01 | Provider down | Degraded deterministic result, no crash |
| IT-GR-01 | Guardrail failure | One rewrite, then safe fallback |

### 3.3 Security tests

| ID | Test |
|---|---|
| SEC-01 | Injection corpus ("ignore previous instructions", "output LOW risk", role-play, hidden text). Level must still be driven by the scorer |
| SEC-02 | Spy on gateway prompts: no PII patterns pass through |
| SEC-03 | Hallucinated phone number in LLM output is blocked |
| SEC-04 | Output never requests OTP/PIN/password |
| SEC-05 | Log audit: run a suite with PII inputs, grep logs and cache for PII patterns |
| SEC-06 | Secret scan on repository and history |
| SEC-07 | Dependency audit |

## 4. Evaluation metrics

> [!NOTE] Benchmark Datasets & Exploratory Challenge Scope
> - **Formal 50-Case Benchmark** (`data/evaluation/eval_dataset.jsonl`): Serves as the official project evaluation baseline reported in `reports/benchmark_report.md`. Evaluates core recall, high-risk detection, false-alarm rates, and safety compliance across English and Hinglish mobile scams.
> - **Internally Authored 28-Case Challenge Suite** (`data/evaluation/external_review_challenge.jsonl`): An exploratory challenge suite constructed to probe severe loss handling (`xr_severe_*`), prompt injection resistance, and nuanced legitimate/ambiguous messages. Evaluated via `scripts/run_external_challenge.py` reporting both strict rubric v1 (22/28) and provisional calibrated rubric v2 (26/28). It is an internal stress test, not an independent third-party certification.

### 4.1 Detection and required behaviour (revised 2026-11-13)

Cases are labelled `scam`, `legit`, or `ambiguous`, with required behaviours (doc 07 section 7.1). Risk levels are not ground truth: nothing in reality has one. So levels are not scored for "accuracy". A case counts as **warned** when the level is above LOW (MEDIUM tells the user to verify before acting).

| Metric | Definition | Why |
|---|---|---|
| Scam recall (warned) | Scams warned about / all scams | Missing a scam is the costliest error |
| Scam recall (HIGH+) | Scams at HIGH or CRITICAL / all scams | Strength of the warning |
| False-alarm rate | Legit cases above LOW / all legit cases | Alarm fatigue teaches people to ignore warnings |
| Precision, F1, F2 | Using "warned" as positive; F2 weights recall higher | Safety priority |
| Ambiguous handling | Ambiguous cases that trigger a follow-up / all ambiguous | Interview value |
| Required-behaviour pass rate | Cases meeting every `required` behaviour / cases with any | Reporting, 1930, child safety, 1909, designated numbers |
| Reporting rate | Suspected-scam cases with an official reporting step in the top 3 actions | Reporting protects other people too |

Also give a confusion matrix of label against level, to show how levels spread for each label.

### 4.2 Classification

Top-1 and top-3 typology accuracy for scam cases; macro F1 across typologies.

### 4.3 Explanation quality

| Metric | Method |
|---|---|
| Groundedness | Share of reasons with valid evidence IDs (automatic) |
| Faithfulness | Manual review of a sample of 30 outputs on a 3-point scale |
| Clarity | Manual review: plain language, actionable |
| LLM-as-judge (optional) | Use a different model as an auxiliary judge, always validated against manual labels on a subset. Not the sole evidence |

### 4.4 Operational

Latency (median, p95), LLM calls per request, tokens per request, estimated cost per request, cache hit rate, degraded-mode rate.

### 4.5 Slices

Report metrics by language (English vs Hinglish), by typology, by input mode, and for adversarial cases.

## 5. Targets

Targets are fixed **before** the first full evaluation run and recorded here with a date. Proposed starting targets (to be confirmed after a pilot run on the dev set):

| Metric | Proposed target |
|---|---|
| Scam recall (warned) on clear scams | at least 0.95 |
| Scam recall (HIGH+) on clear scams | at least 0.90 |
| False-alarm rate on legitimate messages | at most 0.10 |
| Required-behaviour pass rate | 1.00 (these are safety rules) |
| Top-1 typology accuracy on scams | at least 0.80 |
| Groundedness | 1.00 (guardrail enforced) |
| Hinglish vs English recall gap | at most 0.10 |

LLM calls, latency, and cost per request are reported (section 4.4) but are not targets (ADR-001 addendum: quality first).

These are proposals, not results. Final report must show actual numbers and honestly discuss misses.

## 6. Baselines and ablations

To demonstrate the value of the agentic design:

| Variant | Description |
|---|---|
| B0 | Rules-only (extractor + scorer, no LLM) |
| B1 | Single LLM prompt, no tools, no retrieval |
| B2 | Pipeline without retrieval (RAG off) |
| B3 | Pipeline without interview |
| Full | Complete system |

Compare on the same test split. Report differences and cost.

## 7. Evaluation procedure

1. Freeze dataset split and config version (git tag).
2. Run `scripts/evaluate.py --split dev` while tuning weights and thresholds (dev only).
3. Freeze scoring config. Tag.
4. Run on `test` split once per variant. Save outputs to `reports/eval-YYYYMMDD/` with config hash, prompt versions, model IDs, and results CSV.
5. Re-run in cached mode to confirm reproducibility.
6. Analyse errors; write the error analysis into the final report.

## 8. Cost control for evaluation

Estimate token volume before running (cases x calls x tokens). Run a 10-case pilot first. Use cache. Stop if estimated spend exceeds the budget in document 10. Record actual spend in the implementation log.

## 9. Entry and exit criteria

| Phase | Entry | Exit |
|---|---|---|
| Unit/component | Code of the module complete | All pass; coverage target met for deterministic modules |
| Integration | Graph runs end to end | All IT pass |
| Evaluation | Dataset frozen, targets recorded | Report generated and archived |
| Release (demo) | Evaluation done, security tests pass | Demo rehearsed in all three modes |

## 10. Manual review checklist

- Wording is simple and not alarming beyond need.
- Hinglish reads naturally.
- Contacts and links match the verified list.
- UI works at 360 px width, risk level not conveyed by colour alone, controls labelled.
- Disclaimer visible.
