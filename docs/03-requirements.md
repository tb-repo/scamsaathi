# 03. Requirements Specification

| Field | Value |
|---|---|
| Version | 0.1 (Draft) |
| Date | 2026-11-11 |
| Priority scale | MUST (MVP), SHOULD (target), COULD (stretch) |

## 1. User stories

| ID | Story |
|---|---|
| US-1 | As a user, I paste a suspicious message and get a risk level with reasons so I can decide quickly. |
| US-2 | As a user, I describe a phone call in my own words (English or Hinglish) and get an assessment. |
| US-3 | As a user, when my description is incomplete, the assistant asks me short follow-up questions. |
| US-4 | As a user, I get clear next steps, including who to report to. |
| US-5 | As a user, I can get a short summary or complaint draft to share or file. |
| US-6 | As a user, I trust that my phone numbers and account numbers are not stored or leaked. |
| US-7 | As a family helper, I can check a message on behalf of someone else. |
| US-8 | As an evaluator, I can see how the system decided (trace) and its measured accuracy. |

## 2. Functional requirements

### 2.1 Input and intake

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-001 | Accept free-text input up to a configured maximum length (default 4,000 characters). | MUST | US-1, US-2 |
| FR-002 | Detect input language among English, Hinglish, and Hindi (Devanagari); route unsupported languages to a graceful "limited support" response. | MUST | US-1 |
| FR-003 | Classify input mode: pasted message, call/situation description, or question about a specific entity (URL, number, UPI ID). | SHOULD | US-1, US-2 |
| FR-004 | Reject empty or oversized input with a clear error. | MUST | US-1 |
| FR-005 | Accept an optional screenshot and extract text by OCR. | COULD | US-1 |

### 2.2 Signal extraction

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-010 | Extract URLs, phone numbers, UPI IDs, email addresses, and monetary amounts using deterministic patterns. | MUST | US-1 |
| FR-011 | Extract behavioural signals: urgency, threat, secrecy demand, authority impersonation, credential request, payment request, app install request, too-good-to-be-true reward. | MUST | US-1 |
| FR-012 | Identify the impersonated organisation (for example bank, courier, police) when present. | SHOULD | US-1 |
| FR-013 | Output extraction as a typed schema with a confidence value per signal. | MUST | US-8 |

### 2.3 Knowledge and threat intelligence

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-020 | Retrieve the top-k scam typology entries relevant to the extracted signals from the knowledge base. | MUST | US-1 |
| FR-021 | Analyse URLs for risk heuristics: lookalike domains, suspicious TLDs, URL shorteners, IP-based hosts, excessive subdomains, punycode. | MUST | US-1 |
| FR-022 | Look up phones, UPI IDs, and domains in a local blocklist and allowlist. | MUST | US-1 |
| FR-023 | Optionally query an external reputation service (for example Google Safe Browsing) when configured. | COULD | US-1 |
| FR-024 | Compare mentioned organisations against a known-official-domain list. | SHOULD | US-1 |

### 2.4 Classification, scoring, and explanation

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-030 | Classify into one or more scam typologies with a confidence value, or "no scam pattern detected". | MUST | US-1 |
| FR-031 | Compute a numeric risk score (0 to 100) with a deterministic rules-and-weights module. | MUST | US-1, US-8 |
| FR-032 | Map score to levels: LOW, MEDIUM, HIGH, CRITICAL, with thresholds in configuration. | MUST | US-1 |
| FR-033 | Produce an explanation listing the evidence signals that contributed, in plain language. | MUST | US-1, US-8 |
| FR-034 | The LLM may adjust a score only within a bounded range, and each adjustment must be logged with a reason. | SHOULD | US-8 |
| FR-035 | Always state uncertainty and avoid absolute claims ("this is definitely a scam" or "this is definitely safe"). | MUST | US-1 |

### 2.5 Interview (human in the loop)

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-040 | When confidence is below a threshold or critical facts are missing, ask up to N (default 3) follow-up questions. | MUST | US-3 |
| FR-041 | Follow-up questions are short, in the user's language, and answerable by yes/no or a short phrase. | SHOULD | US-3 |
| FR-042 | Maintain session state across turns and resume the workflow after the user answers. | MUST | US-3 |
| FR-043 | If the user does not answer, produce a best-effort assessment with stated uncertainty. | MUST | US-3 |

### 2.6 Advisory and reporting

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-050 | Provide prioritised next steps based on typology and risk level (for example: do not pay, do not share OTP, block, contact bank). | MUST | US-4 |
| FR-051 | Include India-specific reporting channels: National Cyber Crime Helpline 1930, cybercrime.gov.in, and the DoT Sanchar Saathi portal where relevant. Contact details must be verified before release (see R-009). | MUST | US-4 |
| FR-052 | If the user indicates money was already sent or credentials shared, switch to an urgent recovery-steps flow (call bank, call 1930 immediately). | MUST | US-4 |
| FR-053 | Generate a structured summary / complaint draft (text, optionally PDF) with PII masked by default. | SHOULD | US-5 |
| FR-054 | Provide a shareable short summary for family helpers. | COULD | US-7 |

### 2.7 Guardrails and privacy

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-060 | Mask PII (phone numbers, account/card numbers, Aadhaar, PAN, emails, UPI IDs) before any text is sent to an external LLM or written to logs, except where the value itself is the object of a reputation lookup performed locally. | MUST | US-6 |
| FR-061 | Do not persist raw user input by default. | MUST | US-6 |
| FR-062 | Validate the final answer against a schema and a safety checklist before returning it. | MUST | US-1 |
| FR-063 | Detect and neutralise prompt injection in user-supplied text (the user text is data, never instructions). | MUST | US-1 |
| FR-064 | Never ask the user for OTPs, PINs, passwords, or full card numbers. | MUST | US-6 |
| FR-065 | Display a disclaimer that the output is advisory. | MUST | US-1 |

### 2.8 Platform

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-070 | Expose a REST API (FastAPI) for analyse, answer-followup, and health. | MUST | US-1 |
| FR-071 | Provide a mobile-friendly web UI (Streamlit or Gradio, final choice in ADR-005). | MUST | US-1 |
| FR-072 | Provide an LLM abstraction layer with provider and model selection by configuration. | MUST | US-8 |
| FR-073 | Cache LLM responses on disk, keyed by a hash of the masked prompt and model. | MUST | US-8 |
| FR-074 | Provide an offline demo mode that runs entirely from cache and deterministic components. | MUST | US-8 |
| FR-075 | Record a structured trace per request (node, duration, tokens, cost estimate) without raw PII. | MUST | US-8 |
| FR-076 | Enforce a per-request LLM call cap and a daily call/cost budget. | MUST | US-8 |
| FR-077 | Collect optional user feedback (helpful / not helpful, was it a scam). | COULD | US-8 |

### 2.9 Regulatory (added 2026-11-12, see document 16 and ADR-009)

| ID | Requirement | Priority | Story |
|---|---|---|---|
| FR-080 | Accept input only by user paste or typing. Never read SMS inboxes, call logs, contacts, or notifications on the device. | MUST | US-6 |
| FR-081 | Never add a designated-series number (140xx, 1600xx, 1601xx) to the blocklist or label it as a scam or spam number; assess the message content and note that the series is reserved for regulated senders. | MUST | US-1 |
| FR-082 | Treat a claim to be a bank, regulated financial entity, or government body made from an ordinary mobile number or an international number as a risk signal. | SHOULD | US-1 |
| FR-083 | Do not state applicable law sections, charges, or punishments in user assessments; complaint drafts contain facts only. | MUST | US-5 |
| FR-084 | Show a data-use notice before the first analysis: what is processed, what is sent to the AI provider (masked text), what is kept and for how long. | MUST | US-6 |
| FR-085 | Route reporting by situation: spam to 1909 (call or SMS, or the TRAI DND app, within 7 days) and Chakshu "Report Spam (UCC)", suspected fraud to Chakshu, money lost to 1930 and NCRP. Implemented 2026-11-12; 1909 added 2026-11-13 (doc 16 sections 11, 12). | SHOULD | US-4 |
| FR-086 | Recognise TRAI DLT sender headers with a type suffix (-P, -S, -T, -G) and explain the type as information only. Never score, tag, or label a header; assess the content on its own signals. Added 2026-11-13 (doc 16 section 12.2). | SHOULD | US-1 |
| FR-087 | Do not offer an in-app "report spam" option or keep spam reports; point users to official channels only (1909, TRAI DND app, Chakshu). Added 2026-11-13 (TCCCPR Third Amendment 2026). | MUST | US-4 |

## 3. Non-functional requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| NFR-001 | Performance | Median end-to-end latency for a clear-cut input (fast path) | At most 5 s (TBD after measurement) |
| NFR-002 | Performance | 95th percentile latency for the full path with retrieval and strong model | At most 15 s (TBD after measurement) |
| NFR-003 | Cost | Average LLM calls per request | At most 4 (configurable cap) |
| NFR-004 | Cost | Cost per request estimate logged | 100% of requests |
| NFR-005 | Reliability | Graceful degradation if LLM provider fails: fall back to deterministic result with notice | 100% |
| NFR-006 | Reliability | Retry with exponential backoff on 429/5xx | Max 3 retries |
| NFR-007 | Determinism | Same input in cached mode yields same risk level | 100% |
| NFR-008 | Security | No secrets in source or logs | 0 findings in secret scan |
| NFR-009 | Privacy | No raw PII in logs or cache keys | 0 findings in log audit |
| NFR-010 | Usability | Reading level suitable for general users; short sentences | Reviewed manually |
| NFR-011 | Usability | UI usable on a 360 px wide screen | Manual check |
| NFR-012 | Accessibility | Sufficient colour contrast, not colour-only risk indication, labelled inputs | Manual checklist (full WCAG validation requires assistive technology testing) |
| NFR-013 | Maintainability | Type hints, linting, modular agents, unit test coverage for deterministic modules | At least 80% on deterministic modules |
| NFR-014 | Observability | Structured JSON logging with request ID | 100% |
| NFR-015 | Portability | Runs on Windows with Python 3.11 or newer and no GPU | Verified |
| NFR-016 | Explainability | Each verdict carries an evidence list | 100% |
| NFR-017 | Compliance | Alignment with India DPDP Act principles (data minimisation, purpose limitation) documented | Documented in 08 |
| NFR-018 | Quality / accuracy (O-7) | Detection recall, false positive rate, level accuracy, and per-language gap meet the targets in document 09 on the frozen test split | Targets in doc 09 section 5 |
| NFR-019 | Quality / accuracy (O-7) | 100% of reasons carry valid evidence IDs and all contacts come from the verified list (no fabricated facts) | Guardrail plus SEC-03 |
| NFR-020 | Quality (O-7) | Explanation faithfulness and clarity rated acceptable in manual review of a sample | At least 80% rated good on a 3-point scale (proposed) |

## 4. Constraints and assumptions

See document 01 (constraints CON-1 to CON-5) and document 12 (assumptions).

## 5. Traceability matrix (requirements to design and tests)

| Requirement | Design element (doc) | Verified by (doc 09) |
|---|---|---|
| FR-001, FR-004 | API validation (04, 06) | UT-API-01, UT-API-02 |
| FR-002 | Intake agent, language tool (05, 06) | UT-LANG-01, EV-LANG |
| FR-010 | Entity extractor (06) | UT-ENT-01 to UT-ENT-08 |
| FR-011, FR-012, FR-013 | Signal Extraction agent (05) | IT-SIG-01, EV-SIG |
| FR-020 | Pattern Classifier + KB (05, 07) | IT-RAG-01, EV-CLS |
| FR-021 | URL analyzer (06) | UT-URL-01 to UT-URL-10 |
| FR-022, FR-024 | Reputation tool (06, 07) | UT-REP-01 to UT-REP-05 |
| FR-030 | Pattern Classifier (05) | EV-CLS |
| FR-031, FR-032 | Risk scorer (06) | UT-SCORE-01 to UT-SCORE-12 |
| FR-033, FR-035 | Explanation agent (05) | EV-EXPL, MR-01 |
| FR-034 | Scorer + explanation (05, 06) | UT-SCORE-13 |
| FR-040 to FR-043 | Interview agent, checkpointing (04, 05) | IT-INT-01 to IT-INT-04 |
| FR-050 to FR-054 | Advisory agent, report tool (05, 06) | IT-ADV-01 to IT-ADV-05 |
| FR-060, FR-061 | PII masker, guardrail (06, 08) | UT-PII-01 to UT-PII-10, SEC-02 |
| FR-062, FR-063, FR-064 | Guardrail agent (05, 08) | SEC-01, SEC-03, SEC-04 |
| FR-070, FR-071 | API, UI (04) | IT-API-01, MR-02 |
| FR-072 to FR-076 | LLM gateway (04, 06) | UT-LLM-01 to UT-LLM-08 |
| NFR-001 to NFR-004 | Telemetry (04) | PERF-01 to PERF-03 |
| NFR-018 to NFR-020 | Scorer, guardrail, evaluation harness (05, 06, 09) | EV- suite, SEC-03, MR-01 |
| FR-080 to FR-087 | Doc 16, ADR-009; entities and intel tools, advisory, UI | UT-REG-01..05 and TRAI tests in `tests/unit/test_legal_review_features.py` |

## 6. Acceptance criteria (examples)

- **FR-031/032:** Given a message containing an OTP request, a bank impersonation, and a shortened URL, the scorer returns a score at or above the HIGH threshold and the evidence list names all three signals.
- **FR-040/043:** Given the input "they called about my parcel", the system asks at most 3 follow-up questions; if the user stops responding, a LOW/MEDIUM-with-uncertainty result is returned with advice to verify.
- **FR-060:** Given a message containing a 10-digit phone number and a 12-digit Aadhaar number, the prompt captured in the test spy contains placeholders and not the original values.
- **FR-052:** Given "I already sent Rs.5000", the first advice item is to call the bank and 1930.

## 7. Change log

| Version | Date | Change | Author |
|---|---|---|---|
| 0.1 | 2026-11-11 | Initial draft | Thiagarajan Baskarasubramanian |
