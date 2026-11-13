# 02. Business Case and Problem Statement

| Field | Value |
|---|---|
| Version | 0.1 (Draft) |
| Date | 2026-11-11 |

> Statistics are intentionally not quoted here. Before the final report, add current, cited figures (for example from the National Cybercrime Reporting Portal or RBI/NPCI publications) and record the source and access date. Task: see Q-5 in document 12.

## 1. Problem statement

Mobile users in India face frequent scam attempts delivered by SMS, WhatsApp, calls, email, and fake apps. Scammers create urgency, impersonate trusted institutions (banks, police, couriers, government agencies), and push the victim to act within minutes. At that moment the user has no fast, neutral way to ask "is this a scam?" and "what should I do now?".

## 2. Opportunity

An assistant that:

1. Accepts a free-form description or pasted message.
2. Extracts the risky signals.
3. Compares them to known scam patterns and known-bad indicators.
4. Returns a clear risk level with reasons.
5. Tells the user exactly what to do next, including where to report.

## 3. Why an agentic approach

| Need | Why a single prompt falls short | Agentic solution |
|---|---|---|
| Multi-step analysis | Extraction, lookup, reasoning, scoring, advice are different tasks | Specialised agents/nodes with typed state |
| Missing information | A one-shot answer guesses | Interview agent asks targeted follow-up questions |
| Evidence grounding | LLMs hallucinate scam facts | RAG over curated KB and tool lookups |
| Consistent scoring | LLM scores vary run to run | Deterministic scorer, LLM only explains |
| Safety | Free text output can leak PII or give unsafe advice | Guardrail agent checks before returning |
| Cost and latency | Large model on every input is wasteful | Tiered models, cheap path for clear cases |

## 4. Target users and personas

### P-1: Asha, 58, retired teacher

- Uses WhatsApp and UPI, limited tech confidence.
- Receives "your electricity will be cut tonight" and "KYC pending" messages.
- Needs: simple language, a clear "do not pay / do not share OTP" instruction, and who to call.

### P-2: Rohit, 24, first-job professional

- Uses many apps, loan apps, and job portals.
- Receives work-from-home "task" offers and instant loan app ads.
- Needs: explanation of why an offer is suspicious and how the scheme works.

### P-3: Meera, 35, small shop owner

- Accepts UPI payments, receives "payment received, refund excess" requests and QR scams.
- Needs: quick check of a UPI collect request or refund story.

### P-4: Family helper (e.g., adult child)

- Checks a parent's suspicious messages.
- Needs: shareable summary and complaint draft.

## 5. Scam categories in scope (MVP)

| Code | Typology | Typical signals |
|---|---|---|
| SC-01 | Digital arrest / fake law enforcement | Claims of police, CBI, customs; video call; "do not tell anyone"; demand to transfer money for "verification" |
| SC-02 | KYC / account block phishing | Bank or wallet impersonation, link to update KYC, urgency |
| SC-03 | OTP / credential theft | Request for OTP, PIN, CVV, passwords |
| SC-04 | UPI collect / refund scam | Unexpected collect request, "enter PIN to receive money" |
| SC-05 | Fake job / task / part-time work | Pay-to-earn tasks, Telegram groups, advance fee |
| SC-06 | Loan app / harassment | Instant loan, app permission abuse, threats |
| SC-07 | Courier / parcel scam | Held parcel, customs fee, illegal item claim |
| SC-08 | Lottery / prize / gift | Prize claim requiring a fee |
| SC-09 | Investment / trading / crypto | Guaranteed returns, group tips, fake platforms |
| SC-10 | Utility bill / SIM disconnection | "Power cut tonight", "SIM will be blocked" |
| SC-11 | Remote access / fake support | Asks to install a screen-sharing app |
| SC-12 | Romance / impersonation | Emotional manipulation, emergency money request |
| SC-13 | Online money gaming / betting (added 2026-11-12) | Betting or colour-prediction apps, "betting ID", deposit to withdraw |
| SC-14 | Sextortion / morphed-image blackmail (added 2026-11-12) | Threat to share intimate or AI-morphed images unless paid |
| SC-15 | Money mule / account and SIM renting (added 2026-11-12) | Commission for letting others use your account, UPI ID or SIM |

The list is extensible through the knowledge base (document 07).

## 6. Value proposition

- **For users:** Fast second opinion with reasons and actions.
- **For the certification:** A realistic, safety-relevant use case that exercises multi-agent orchestration, RAG, tool use, memory, human-in-the-loop interview, guardrails, evaluation, and cost control.

## 7. Competitive and alternative landscape

| Alternative | Limitation addressed by ScamSaathi |
|---|---|
| Asking a general chatbot | No grounding, no tools, inconsistent, no India-specific reporting guidance |
| Caller ID / spam apps | Cover calls and numbers, not message content or situation reasoning |
| Government portals and helplines | Authoritative but not an instant explainer; ScamSaathi points users to them |
| Friends and family | Not always available, may not know the pattern |

ScamSaathi does not replace official channels. It guides users to them.

## 8. Benefits and success indicators

| Benefit | Indicator |
|---|---|
| Fewer risky actions | Output always includes a clear "do / do not" action list |
| Trust through explanation | Evidence list shown with each verdict |
| Reproducibility | Same input yields same risk level (deterministic scorer, cached LLM text) |
| Low cost | Average LLM calls per request at or below the configured cap |

## 9. Costs (prototype)

| Item | Estimate |
|---|---|
| LLM API | Covered by existing credits; tracked per run (document 10) |
| Embeddings | Free if run locally on CPU, otherwise small API cost |
| Hosting | Local for demo; optional free hosting for a shareable link |
| Effort | Single developer, schedule in document 10 |

## 10. Risks to the business case

Summarised from document 12: false negatives giving false reassurance, false positives causing alarm, privacy concerns, dependency on a single LLM provider, and over-claiming accuracy. Mitigations are in documents 08 and 09.

## 11. Ethical positioning

ScamSaathi is an advisory tool. It states uncertainty, never guarantees safety, and always advises verifying through official channels. See document 08.
