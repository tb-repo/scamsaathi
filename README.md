# 🛡️ ScamSaathi (स्कैम साथी)

<p align="center">
  <strong>An Agentic AI Assistant for Mobile Scam Defense in India</strong><br>
  <em>Protecting citizens against SMS, WhatsApp, and call scams through deterministic guardrails, privacy-preserving multi-agent reasoning, and official recovery guidance.</em>
</p>

<p align="center">
  <a href="#-multi-agent-architecture"><img src="https://img.shields.io/badge/Architecture-9--Agent%20LangGraph-blue.svg?style=flat-square" alt="Architecture" /></a>
  <a href="#-empirical-benchmark-evaluation"><img src="https://img.shields.io/badge/Scam%20Recall-97.2%25-success.svg?style=flat-square" alt="Scam Recall" /></a>
  <a href="#-empirical-benchmark-evaluation"><img src="https://img.shields.io/badge/Safety%20Behaviors-97.7%25-success.svg?style=flat-square" alt="Safety Behaviors" /></a>
  <a href="#-testing--verification"><img src="https://img.shields.io/badge/Pytest-275%20Passed%20(100%25)-brightgreen.svg?style=flat-square" alt="Tests" /></a>
  <a href="#-privacy-by-design--dpdp-act-2023-compliance"><img src="https://img.shields.io/badge/Privacy-DPDP%20Act%20Aligned-darkgreen.svg?style=flat-square" alt="Privacy" /></a>
  <a href="#-quick-start--installation"><img src="https://img.shields.io/badge/Python-3.11%2B-blue.svg?style=flat-square&logo=python&logoColor=white" alt="Python Version" /></a>
  <a href="#-license--capstone-metadata"><img src="https://img.shields.io/badge/Certification-Hero%20Vired%20Agentic%20AI-orange.svg?style=flat-square" alt="Hero Vired Capstone" /></a>
</p>

---

## 📌 Executive Summary

According to data from a presentation on the Citizen Financial Cyber Fraud Reporting and Management System (CFCFRMS) during a PIB-covered media workshop (*PIB Press Release dated 21 August 2026, PRID 2301973*), Indian citizens reported **₹22,495 crore** in financial cyber fraud losses across **28.15 lakh complaints** in 2025. The presentation data highlighted that **76% of reported financial losses** were concentrated in fake investment and trading scams, alongside rampant digital arrest intimidation, part-time job fraud, and phishing messages.

Traditional defense tools fail because:
1. **Static keyword filters & regex** miss evolving social engineering tactics and trigger high false alarm rates on legitimate banking alerts (`.bank.in`).
2. **Pure LLM solutions** hallucinate fake helplines, exhibit unpredictable risk scoring, leak private user data to third-party APIs, and cannot enforce strict safety floors.

**ScamSaathi** solves this with a **Deterministic-First Agentic Architecture**:
- **Deterministic Pre-Screen & Rules Engine**: Checks official TRAI service codes (1600/1601), authenticated banking domains (`.bank.in`, `.gov.in`), and known malicious URLs before LLMs are invoked.
- **Privacy-by-Design Masking**: Replaces phone numbers, bank accounts, UPI IDs, emails, and contextual OTPs with local tokens before prompts leave the machine.
- **Stateful Multi-Agent Reasoning (LangGraph)**: Employs 9 specialized agents to extract psychological urgency signals, classify against 15 curated cyber fraud typologies (SC-01 through SC-15), score risk (0–100) within bounded delta limits, and cite deterministic evidence IDs (`S#`, `I#`, `K#`, `C#`).
- **Human-in-the-Loop (HITL) Clarification & Actor Scoping**: Distinguishes first-person compromise from third-party actions or hearsay; tracks structured exposure facts (`confirmed`, `denied`, `unknown`) and triggers targeted single-fact clarifying follow-ups on ambiguous reports rather than hallucinating answers.
- **Official Citizen Recovery Guidance**: Directly routes victims to the **DoT Chakshu Facility**, the **National Cyber Crime Reporting Portal**, and the **1930 Financial Fraud Helpline** for golden-hour loss mitigation.

---

## 🏗️ Multi-Agent Architecture

The ScamSaathi architecture strictly separates access, application execution, external AI gateways, and user-directed reporting into 4 clear architectural zones:

![ScamSaathi Current Implementation Architecture](docs/ScamSaathi_Architecture.svg)

### The 4 Architectural Zones

1. **Access & Experience Zone (Untrusted Input Boundary)**:
   - **Streamlit Web Application** (`src/scamsaathi/ui/streamlit_app.py`): Interactive citizen portal with sample scam presets, visual risk gauges, evidence breakdowns, and bilingual (English/Hinglish) support.
   - **FastAPI REST Service** (`src/scamsaathi/api/app.py`): Secure API featuring cryptographic session token verification (`X-Session-Token`), sliding-window rate limiting (60 req/min), and automated 24-hour TTL pruning.
   - **Air-Gapped Offline CLI** (`scripts/run_agentic.py`): Demonstrates full multi-agent graph execution across canonical scenarios without internet or external API dependencies.

2. **ScamSaathi Application Boundary (Python Runtime)**:
   - **A1: Intake & Local Masker**: Detects language (EN / Hinglish) and replaces sensitive identifiers (`<PHONE_1>`, `<BANK_ACC_1>`, `<UPI_ID_1>`, `<EMAIL_1>`, `<OTP_1>`).
   - **A2: Feature / Signal Extractor**: Identifies urgent financial coercion, authority impersonation, and structural suspicious patterns.
   - **A3: Threat Intel DB**: SQLite-backed verification of TRAI 1600/1601 series, designated bank domains (`.bank.in`), and blocklisted domains/handles (runs straight after intake).
   - **Deterministic Prescreen**: Applies fast-path rules and calculates deterministic baseline scores.
   - **A4: Classifier Agent**: Maps threats to 15 curated typologies (SC-01 to SC-15) and identifies missing situational facts.
   - **A5: Interview / Question Planner**: Pauses graph execution with LangGraph `interrupt()` when ambiguous reports require user clarification; resolves situational exposure facts (distinguishing personal OTP entry from caller demonstrations, or user sideloading from technician testing) without adding inferred claims.
   - **A6: Deterministic Scorer**: Computes calibrated 0–100 risk score combining rule signals, threat intelligence, safety floors (`urgent_recovery`, `blocklist_floor`, `child_safety`), and applies a bounded LLM scoring adjustment (capped at $\pm 10$ points from baseline).
   - **A7: Explainer & A8: Advice Agents**: Unified in a single model call (`explain_advise`), A7 synthesizes evidence-grounded explanations citing runtime IDs (`S#`, `I#`, `K#`, `C#`) while A8 formulates prioritized citizen action steps and verified emergency reporting channels.
   - **A9: Post-Graph Guardrail Sanitizer**: Runs after graph completion as a final safety gate to suppress PII leakage, block absolute safety claims, suppress specific legal sections (FR-083), prevent secret demands (FR-064), validate official contact allowlists (FR-050), and attach mandatory advisory disclaimers (FR-065). *(Note: ephemeral raw text vault clearance is performed upon session completion by `AgentRunner.clear_session`).*

3. **External Services Trust Boundary (Masked Prompts Only)**:
   - **LLM Gateway with Circuit Breakers**: Primary execution uses Google Gemini (`gemini-3.5-flash-lite` fast tier, `gemini-3.8-flash` reasoning tier) with `gemini-3.6-flash` reasoning fallback defined in `config/llm.yaml`. Multi-provider Groq fallback (`llama-3.1-8b-instant` fast, `llama-3.3-70b-versatile` reasoning) is dynamically activated when a `GROQ_API_KEY` is configured in the environment.
   - **Ephemeral In-Memory Vault**: Raw unmasked text is held exclusively in memory during graph execution and popped immediately upon assessment completion.

4. **User-Directed Reporting Guidance (Verified Official Channels)**:
   - **DoT Chakshu Facility**: Suspected fraud communication reporting (`sancharsaathi.gov.in/sfc`).
   - **National Cyber Crime Portal**: Official suspect registry for phone numbers, UPI IDs, and URLs (`cybercrime.gov.in`).
   - **1930 Financial Fraud Helpline**: Golden-hour recovery reporting and bank coordination assistance (lien/freezing decisions remain the statutory remit of banks and law enforcement authorities).

---

## 🔄 9-Agent StateGraph Execution Flow

```
                     [Citizen Input (Text / Transcript)]
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │            intake             │ ── Language detection & local PII masking
                     └───────────────────────────────┘
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │             intel             │ ── Threat intel lookup (TRAI 1600, .bank.in, URLs)
                     └───────────────────────────────┘
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │            extract            │ ── Urgent coercion & entity pattern extraction
                     └───────────────────────────────┘
                                     │
                                     ▼
                     ┌───────────────────────────────┐
                     │           prescreen           │ ── Rule baseline score & fast-path evaluation
                     └───────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │ (needs LLM reasoning)           │ (clear rules / fast-path)
                    ▼                                 │
             ┌─────────────┐                          │
             │  classify   │ (SC-01 to SC-15)         │
             └─────────────┘                          │
                    │                                 │
             ┌──────┴──────┐                          │
      (ambiguous)     (conclusive)                    │
             ▼             │                          │
     ┌───────────────┐     │                          │
     │ plan_questions│     │                          │
     └───────────────┘     │                          │
             │             │                          │
             ▼             │                          │
     ┌───────────────┐     │                          │
     │ await_answers │(HITL Interrupt)                │
     └───────────────┘     │                          │
             │             │                          │
             └──────┬──────┘                          │
                    ▼                                 ▼
             ┌──────────────────────────────────────────────┐
             │                    score                     │ ── Calibrated 0-100 score & safety floors
             └──────────────────────────────────────────────┘
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │                explain_advise                │ ── Evidence grounding (A7) & advice (A8) [unified call]
             └──────────────────────────────────────────────┘
                                    │
                                    ▼
                             [StateGraph END]
                                    │
                                    ▼
             ┌──────────────────────────────────────────────┐
             │            A9: GuardrailSanitizer            │ ── Post-graph PII, safety & allowlist gate
             └──────────────────────────────────────────────┘
                                    │
                                    ▼
                        [Final Assessment Outcome]
```

---

## 📋 The 15 Supported Cyber Fraud Typologies (ScamSaathi Knowledge Base)

ScamSaathi classifies incoming messages against a curated 15-category mobile scam taxonomy modeled on prevailing Indian cyber threats and public advisories (`data/kb/typologies`):

| Code | Typology Name | Primary Attack Channels | Typical Manipulation Signals | Primary Defense Guidance |
| :---: | :--- | :--- | :--- | :--- |
| **SC-01** | Digital Arrest / Fake Law Enforcement | Video Calls (Skype/WhatsApp), IVR | Claims of CBI/ED/Police, "stay on call", fake warrants | **Immediate Disconnect** / 1930 / MHA |
| **SC-02** | KYC / Account Block Phishing | SMS, WhatsApp, IVR | Bank impersonation, urgent deactivation, phishing link | Bank official app / DoT Chakshu |
| **SC-03** | OTP / Credential Theft (Vishing) | Phone Calls, SMS | Urgent request for OTP, PIN, CVV, or netbanking login | Never share OTP / Bank helpline |
| **SC-04** | UPI Collect / QR "Receive Money" Scam | WhatsApp, Olx/Marketplaces | Unexpected collect request, "enter PIN to receive funds" | Decline request / Never enter PIN |
| **SC-05** | Fake Job / Task-Based Part-Time Work | Telegram, WhatsApp | YouTube like tasks, prepaid orders, Telegram groups | Cyber Crime Portal / Freeze transfers |
| **SC-06** | Predatory Loan App Blackmail | Malicious APKs, SMS | Instant loan without KYC, contacts access, extortion | Uninstall APK / Cyber Crime / Police |
| **SC-07** | Courier / Customs Parcel Trap | Phone Calls, IVR, SMS | Held package (FedEx/DHL), drugs/contraband claim | Verify on courier portal / Chakshu |
| **SC-08** | Lottery / Prize / Gift Advance Fee | WhatsApp, SMS | KBC / lucky draw winner, advance processing fee | Never pay fee / Chakshu |
| **SC-09** | Investment / Trading / Crypto Fraud | WhatsApp Groups, Social Media | Guaranteed high returns, VIP trading tips, fake dashboard | SEBI SCORES / 1930 / Cyber Crime |
| **SC-10** | Utility Bill / SIM Disconnection Scam | SMS, WhatsApp | "Power cut tonight", "SIM blocked within 24h", call officer | Official Discom / Telecom store |
| **SC-11** | Remote Access / Fake Customer Support | SMS, Google Ads, Phone | Remote screen-sharing apps (AnyDesk, TeamViewer) | Never install app / Disconnect |
| **SC-12** | Impersonation / Romance Scam | Social Media, Matrimonial | Emergency distress story from friend/relative or love interest | Independent voice check / Never send funds |
| **SC-13** | Online Money Gaming / Betting Scam | Social Media, Telegram | Color-prediction apps, betting IDs, deposit to withdraw | Block app / Cyber Crime Portal |
| **SC-14** | Sextortion / Morphed-Image Blackmail | WhatsApp, Video Calls | Video call blackmail, threat to share morphed images | **Do Not Pay** / 1930 / Cyber Crime |
| **SC-15** | Money Mule / Account & SIM Renting | Telegram, Social Media | Commission to receive transfers or rent bank/SIM credentials | Reject offer / Report to Cyber Crime |

---

## 📊 Empirical Benchmark Evaluation

Evaluation across the internal 50-case benchmark dataset (`reports/benchmark_report.md`):

| Evaluation Metric | Target | Baseline B0 (Rules) | Full Agentic (Ours) | Delta / Achievement | Verification Level |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Scam Recall (Warned > LOW)** | $\ge 95.0\%$ | 47.2% | **97.2%** | **+50.0 pp** | 35/36 scams detected; catches subtle social engineering |
| **High-Risk Recall (HIGH/CRITICAL)** | $\ge 90.0\%$ | 25.0% | **75.0%** | **+50.0 pp** | 27/36 scams escalated to HIGH/CRITICAL |
| **False Alarm Rate (Legit > LOW)** | $\le 10.0\%$ | 0.0% | **9.1%** | Target Met | 0% false alarms on authentic `.bank.in` & TRAI headers |
| **Required Safety Behaviors** | 100.0% | 100.0% | **97.7%** | -2.3 pp Gap | 43/44 behaviors met (1930 recovery, child safety) |
| **Typology Accuracy (Exact Top-1)** | $\ge 80.0\%$ | N/A | **97.1%** | **+17.1 pp** | 34/35 primary typologies classified accurately |
| **Typology Top-3 Coverage** | $\ge 90.0\%$ | N/A | **97.1%** | **+7.1 pp** | Primary typology included in top 3 predictions |
| **Evidence-ID Grounding Rate** | 100.0% | N/A | **100.0%** | **Target Met** | 100% citation consistency against runtime state (`S#`, `I#`, `K#`, `C#`) |
| **Non-Devanagari Script Compliance** | 100.0% | 100.0% | **100.0%** | **Target Met** | Character-level audit: 0% Devanagari script leakage |
| **Official Reporting Guidance** | N/A | N/A | **97.2%** | Active Value | Chakshu (88.9%), Cyber Crime (94.4%), 1930 (100% loss) |
| **Ambiguous Case Clarification** | 100.0% | 0.0% | **66.7%** | Proactive HITL | 2/3 ambiguous reports successfully triggered interview |
| **All-Checks Pass Rate** | N/A | 62.0% (31/50) | **90.0% (45/50)** | **+28.0 pp** | 45 of 50 cases passed 100% of all criteria (0 errors) |
| **Median Execution Latency** | $< 5000\text{ ms}$ | 5.4 ms | **191.9 ms** (Cached) | Instantaneous | Within Target (< 5000 ms) |

### Bilingual Performance Slices (English vs. Hinglish)

| Language Slice | Total Scams | Scams Warned | Recall Rate | Genuine Messages | False Alarms | False Alarm Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **English (EN)** | 20 | 19 | **95.0%** | 10 | 1 | 10.0% |
| **Hinglish (HI-EN)** | 16 | 16 | **100.0%** | 1 | 0 | **0.0%** |

### Audit Notes & Transparent Metric Disclosures

> **Case-Level Execution Audit**: Across all 50 evaluated cases, execution completed with **0 pipeline or runtime errors**. **45 out of 50 cases (90.0%)** passed every core, safety, and typology criterion. The 5 specific criteria failures directly explain observed metrics:
> - `eval_34`: 1 subtle digital arrest scam missed with a LOW score, driving the 97.2% recall rate (35/36 scams detected).
> - `eval_38`: 1 false alarm on a legitimate bank statement, driving the 9.1% false-alarm rate (1/11).
> - `eval_05`: Advisory ordering gap where reporting was outside top 3 actions, driving the 97.7% safety score (43/44).
> - `eval_22`: Top-1 typology mismatch, driving the 97.1% top-1 accuracy (34/35).
> - `eval_45`: Ambiguous case resolved directly without interview, driving the 66.7% clarification rate (2/3).
>
> **High-Risk Recall Gap**: `check_core()` evaluates binary scam recall (scam cases must receive risk > LOW). In addition to `eval_34`, **8 detected scams received a `MEDIUM` risk level** rather than being escalated to `HIGH` or `CRITICAL`, explaining the 75.0% (27/36) high-risk recall versus the $\ge 90.0\%$ target.
>
> **Baseline B0 Comparability Caveat**: Baseline B0's 62.0% (31/50) all-checks pass rate measures only rule-based warning triggering on scams and absence of false alarms on clean messages. Because Baseline B0 produces neither typologies nor advice, advice-specific checks are bypassed. In contrast, Full Agentic's 90.0% (45/50) evaluates the complete multi-dimensional criteria suite (warning, 15-typology classification, evidence citations, and official citizen reporting guidance).

---

## 🔒 Privacy by Design & DPDP Act 2023 Compliance

ScamSaathi implements strict data minimization, purpose limitation, and storage limitation. Retention policies are tailored specifically to each interface:

### 1. Streamlit Web Application (`src/scamsaathi/ui/streamlit_app.py`)
- **Zero Device Scraping**: Operates purely via web paste; requests no access to device SMS, contacts, or call logs.
- **Ephemeral In-Memory Vault**: Raw unmasked text exists in an in-memory vault solely during graph execution and is popped immediately once analysis completes.
- **Immediate Completed Outcome Purge**: When an assessment or resumed interview finishes (`status == "complete"`), LangGraph checkpoints and in-memory PII mappings are purged immediately (`runner.clear_session(thread_id, purge_checkpoint=True)`), and thread tracking is reset.
- **Paused Interview Inactivity TTL**: For ambiguous cases awaiting user answers (`status == "needs_followup"`), checkpoints remain in memory to support resumption. On the next user interaction after **30 minutes of inactivity**, the UI automatically purges the runner session, clears the stored outcome, and resets the input widget.
- **Explicit User Clear**: Clicking the "Clear" button resets all session state, purges checkpoints, and resets inputs.

### 2. FastAPI REST Backend (`src/scamsaathi/api/app.py`)
- **Immediate Completed Outcome Purge**: Completed assessments (`status == "complete"`) have their SQLite `session_meta`, `checkpoints`, and `writes` records purged atomically via `_purge_session_records` before the response is returned. `session_token` in the response is set to `null`.
- **Paused Session Retention & Security**: Paused sessions (`status == "needs_followup"`) retain checkpoint records accompanied by a cryptographically random ownership token (`X-Session-Token`). Only callers presenting the matching token can resume or delete the session.
- **24-Hour TTL & Background Purge**: Active/paused sessions expire after **24 hours**. An hourly background task and lazy assessment checks prune stale sessions; resuming an expired session returns `410 Gone`.
- **Right to Erasure Endpoint**: Callers can call `DELETE /session/{thread_id}` with their token to purge checkpoint records on demand.

---

## 🚀 Quick Start & Installation

### 1. Prerequisites & Environment Setup

ScamSaathi requires **Python 3.11+**.

```bash
# Clone the repository
git clone git@github.com:tb-repo/scamsaathi.git
cd scamsaathi

# Create and activate a virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install authoritative dependencies
pip install -r requirements.lock
# Or install in editable development mode:
pip install -e .
```

### 2. Configuration (`.env`)

Copy the example configuration file and set your API keys:

```bash
cp .env.example .env
```

Key environment configuration variables:
| Variable | Description | Default |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Primary Google Gemini API key (paid tier recommended) | Required |
| `GROQ_API_KEY` | Groq API key for multi-provider fallback | Optional |
| `SCAMSAATHI_MODE` | Operating mode: `live`, `cached`, or `offline` | `live` |
| `GEMINI_MODEL_FAST` | Fast classification model tier | `gemini-3.5-flash-lite` |
| `GEMINI_MODEL_REASONING` | Reasoning & explanation model tier | `gemini-3.8-flash` |
| `SCAMSAATHI_MAX_LLM_CALLS_PER_REQUEST` | Per-request call budget cap | `6` |
| `SCAMSAATHI_TRUSTED_PROXIES` | Trusted reverse proxy IPs for rate limiting | `127.0.0.1,::1,localhost` |

### 3. Running the Streamlit Web Application

```bash
streamlit run src/scamsaathi/ui/streamlit_app.py
```
Open your browser at `http://localhost:8501`.

### 4. Running the FastAPI REST Backend

```bash
uvicorn scamsaathi.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger API documentation is available at `http://localhost:8000/docs`.

### 5. Running the Air-Gapped Offline Demo

Demonstrates the 9-agent pipeline on canonical Indian scam scenarios without requiring internet connectivity or API credits:

```bash
python scripts/run_agentic.py
```

### 6. Running the Benchmark Evaluation Harness

```bash
python scripts/run_benchmarks.py
```

---

## 🧪 Testing & Verification

The project includes a comprehensive offline test suite covering all units, pipelines, and security boundaries:

```bash
pytest -v
```

**Verification Results: 275 passed in 33.64s (100% Passing)**

The test suite validates:
- Deterministic signal extractors and threat intel database queries.
- PII masking, token replacement, and raw vault clearing.
- LangGraph state routing and interrupt/resume cycles.
- Multi-provider LLM gateway caching, retries, and fallback circuit-breakers.
- FastAPI endpoints, cryptographic session ownership tokens, 24h TTL expiration, CORS restrictions, and session deletion.
- Advice engine official contact allowlists and URL validation.

---

## 📁 Repository Structure

```
scamsaathi/
├── config/                 # Gateway model tiers, fallbacks & costs (llm.yaml)
├── data/
│   ├── advice/             # Canonical advice templates (advice.yaml)
│   ├── contacts/           # Verified official Indian reporting channels (contacts.yaml)
│   ├── demo/               # Air-gapped offline gold demo cache
│   ├── evaluation/         # 50-case benchmark evaluation dataset (eval_dataset.jsonl)
│   ├── intel/              # Threat intel blocklists and designated numbers
│   └── kb/                 # Indian cyber fraud typologies (SC-01 to SC-15) & embeddings
├── docs/                   # Full project documentation & architectural decisions
│   ├── 01-charter.md       # Project charter & problem statement
│   ├── 02-user-journeys.md # Persona definitions & user journey maps
│   ├── 03-requirements.md  # Functional (FR) & Non-Functional (NFR) specs
│   ├── 04-architecture.md  # Detailed system architecture & component boundaries
│   ├── 08-security-privacy-responsible-ai.md # DPDP Act compliance & threat model
│   ├── 11-adr/             # Architectural Decision Records (ADR-001 to ADR-009)
│   ├── 14-user-deployment-demo-guide.md # Deployment & live demo instructions
│   ├── 15-legal-regulatory-reference.md # Legal & regulatory reference
│   ├── 16-current-architecture.md       # Architecture walkthrough
│   └── ScamSaathi_Architecture.svg      # Full implementation architecture diagram
├── reports/                # Benchmark evaluation reports & run metadata
│   ├── benchmark_report.md # Generated Markdown benchmark evaluation report
│   └── benchmark_run_meta.json # Detailed per-case metrics & execution metadata
├── scripts/
│   ├── build_kb.py         # Knowledge base builder
│   ├── run_agentic.py      # Air-gapped offline interactive demo
│   └── run_benchmarks.py   # Comprehensive benchmarking harness
├── src/scamsaathi/
│   ├── agents/             # 9 specialized LangGraph agents
│   ├── api/                # FastAPI application, security & Pydantic schemas
│   ├── evaluation/         # Benchmark evaluation metrics & ground truth labels
│   ├── graph/              # LangGraph state graph wiring and node transitions
│   ├── kb/                 # Curated knowledge base store and advice builder
│   ├── llm/                # LLM gateway, disk cache, budget & model providers
│   ├── pipeline/           # AgentRunner & Baseline B0 pipeline
│   ├── prompts/            # Agent prompt templates
│   ├── tools/              # PII masker, threat intel DB, rule signals & risk scorer
│   ├── ui/                 # Streamlit web user interface
│   ├── config.py           # Pydantic Settings & environment loader
│   ├── logging_setup.py    # Structured logging configuration
│   └── schemas.py          # Core Pydantic domain schemas
├── tests/                  # 275 unit and integration tests
├── pyproject.toml          # Project metadata & configuration
├── requirements.txt        # Pinned direct dependencies
├── requirements-dev.txt    # Development and test dependencies
└── requirements.lock       # Authoritative full environment lock
```

---

## 📜 License & Capstone Metadata

- **Program**: Professional Certification in Agentic AI — Capstone Project
- **Institution**: Hero Vired
- **Candidate**: Thiagarajan Baskarasubramanian
- **Date**: November 2026
- **License**: All rights reserved © 2026 Thiagarajan Baskarasubramanian.
