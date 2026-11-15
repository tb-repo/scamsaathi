# 01. Project Charter

| Field | Value |
|---|---|
| Project name | ScamSaathi |
| Version | 1.0 (Approved) |
| Date | 2026-11-11 |
| Author / Project lead | Thiagarajan Baskarasubramanian |
| Context | Capstone project, Agentic AI certification (Hero Vired) |

## 1. Vision

Help everyday mobile users in India recognise scams while they are happening. The user describes a message, call, link, or situation. ScamSaathi (Hindi "saathi" = companion) returns a risk level, plain-language reasons, and safe next steps, so the user can stop before paying or sharing credentials.

## 2. Problem summary

Scams such as UPI collect-request fraud, OTP and KYC phishing, "digital arrest" threats, fake job and task offers, and fake loan apps rely on urgency and impersonation. Victims often lack a quick, trustworthy second opinion at the moment of pressure. Details are in document 02.

## 3. Objectives

| ID | Objective | Measure |
|---|---|---|
| O-1 | Deliver a working multi-agent prototype that assesses scam risk from text input | End-to-end demo runs for all demo scenarios |
| O-2 | Provide explainable output | Every verdict lists the evidence signals it relied on |
| O-3 | Demonstrate sound agentic design | Distinct agents, tools, conditional routing, memory, guardrails |
| O-4 | Demonstrate measurable quality | Evaluation report on a labelled synthetic test set |
| O-5 | Deliver enterprise-grade documentation | Document set 01 to 15 complete and traceable |
| O-6 | Operate within budget | Cost per request and total spend tracked against cap |
| O-7 | Deliver a working prototype that produces high-quality, accurate, and trustworthy responses | Measured on the labelled test set against the targets in document 09 (recall, false positive rate, level accuracy, groundedness, explanation quality), compared with baselines. Accuracy is demonstrated with numbers and error analysis, not asserted |

## 4. Scope

### 4.1 In scope (MVP)

- Text input (pasted SMS, WhatsApp text, email text, or a described call/situation).
- English and Hinglish (Roman-script Hindi). Devanagari Hindi is a stretch goal.
- Entity extraction: URLs, phone numbers, UPI IDs, amounts, organisations impersonated.
- Scam typology classification using a curated knowledge base (RAG).
- URL and domain heuristics, local phone/UPI/domain blocklist lookups.
- Deterministic risk scoring combined with LLM reasoning.
- Follow-up questions when information is insufficient (symptom interview).
- Advice and a draft complaint summary (reporting via 1930 and cybercrime.gov.in).
- PII masking and output guardrails.
- Web UI (mobile-friendly) and REST API.
- Evaluation harness, LLM response cache, and an offline demo mode.

### 4.2 Stretch (only if time allows)

- Screenshot OCR input.
- Devanagari Hindi and other Indian languages.
- Voice or call-recording transcription.
- Feedback-driven knowledge base suggestions.
- Fine-tuned lightweight classifier.

### 4.3 Out of scope

- Real-time interception of calls or SMS on a device.
- Integration with telecom operators, banks, or law enforcement systems.
- Storing real victim data or real personal messages.
- Legal advice or any claim of definitive fraud determination.
- Native Android/iOS app.
- Recovering lost money.

## 5. Deliverables

| ID | Deliverable | Location |
|---|---|---|
| D-1 | Documentation set (01 to 15) | `docs/` |
| D-2 | Kiro spec files (requirements, design, tasks) | `.kiro/specs/` |
| D-3 | Working application (agents, tools, API, UI) | `src/scamsaathi/` |
| D-4 | Knowledge base, synthetic dataset, blocklists | `data/` |
| D-5 | Automated tests and evaluation harness | `tests/` |
| D-6 | Evaluation report | `docs/09-test-evaluation-strategy.md` and `reports/` |
| D-7 | Demo script and recorded fallback demo | `docs/14-user-deployment-demo-guide.md` |
| D-8 | Final report and presentation | Capstone submission package |

## 6. Success criteria

- SC-1: All must-have requirements in document 03 are implemented and traced to tests.
- SC-2: On the labelled test set, scam detection recall is at least the target in document 09 with false positive rate within target (targets are set before the first evaluation run, not after).
- SC-3: Every response includes risk level, reasons tied to evidence, and next steps.
- SC-3a (quality and accuracy, O-7): Responses are factually grounded (no invented contacts, facts, or reasons), correct on the test set within the agreed targets, and judged clear and actionable in manual review. Wrong answers are analysed and reported honestly.
- SC-4: The demo runs reliably, including in offline/cached mode.
- SC-5: No secrets or real personal data in the repository.
- SC-6: LLM spend stays within the budget in document 10.

## 7. Stakeholders

| Stakeholder | Interest | Role |
|---|---|---|
| Thiagarajan Baskarasubramanian | Delivers and presents the project | Project lead, developer, author |
| Certification evaluators | Assess agentic design, working prototype, documentation | Reviewers |
| Target users (mobile users in India) | Safer decisions under pressure | End users (represented by personas) |
| Mentor / instructors (if any) | Guidance | Advisors |

## 8. Assumptions (summary; full list in document 12)

- A-1: Gemini paid tier is active with sufficient credit for development and evaluation.
- A-2: Local models are not used (16 GB RAM laptop, no GPU).
- A-3: Only synthetic or public data is used.
- A-4: The certification does not mandate a different framework (open question Q-1).
- A-5: Target is India-specific.

## 9. Constraints

| ID | Constraint |
|---|---|
| CON-1 | Single developer, part-time effort |
| CON-2 | Laptop with 16 GB RAM, no GPU (Windows) |
| CON-3 | Budget limited to existing credits (about Rs.500 prepaid plus eligible promotional credits; exact usable amount to be verified) |
| CON-4 | Certification deadline (date TBD, Q-2) |
| CON-5 | Python, LangGraph (ADR-002) |

## 10. High-level milestones

See document 10 for the detailed plan. Phases: Documentation, Foundations, Core pipeline, Interview and advisory, Guardrails and UI, Evaluation, Hardening and demo, Final report.

## 11. Governance

- Decisions are recorded as ADRs.
- Changes to requirements go through the change log in document 03.
- Weekly self-review of risks and plan (document 12 and 10).

## 12. Approval

| Role | Name | Status | Date |
|---|---|---|---|
| Author | Thiagarajan Baskarasubramanian | Pending review | - |
