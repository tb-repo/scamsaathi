# ScamSaathi (स्कैम साथी)

**An Agentic AI Assistant for Mobile Scam Defense in India.**

> *Helping citizens identify mobile scams, understand social engineering manipulation, and take safe, official recovery steps before or after financial loss.*

---

| Attribute | Details |
| :--- | :--- |
| **Certification** | Hero Vired — Professional Certification in Agentic AI (Capstone Project) |
| **Author** | Thiagarajan Baskarasubramanian |
| **Architecture** | 9-Agent StateGraph with LangGraph & SQLite Checkpointer |
| **Primary LLMs** | Google Gemini (gemini-3.5-flash-lite / gemini-3.8-flash) |
| **Fallback LLMs** | Groq (llama-3.3-70b-versatile) with Circuit-Breaker Gateway |
| **Scope** | Mobile SMS, WhatsApp, and call transcripts in English & Hinglish |
| **Test Suite** | 259 Unit & Integration Tests (100% Passing) |
| **Evaluation** | 50-Case Comprehensive Benchmark (97.2% Scam Recall, 0% False Alarms on Banking) |

> ⚠️ **Important Safety Disclaimer**: ScamSaathi provides risk assessments and safety guidance, not legal advice or definitive investigative verdicts. Automated masking protects phone numbers, accounts, UPI IDs, emails, and contextual OTPs, but pattern matching cannot reliably redact personal names or street addresses. Always verify independently through official channels.

---

## 🌟 Key Capabilities

1. **Deterministic-First Agentic Defense**:
   - **Deterministic Rules & Threat Intel**: URL blocklists, TRAI designated service series (1600/1601), `.bank.in` / `.gov.in` domain legitimacy verification, and keyword signal extraction run deterministically before LLM invocation.
   - **Bounded LLM Reasoning**: LLMs classify Indian cyber fraud typologies (I4C SC-01 through SC-10) and explain social engineering tactics within bounded score delta limits.
   - **Deterministic Safety Floors**: Overrides enforce strict minimum risk scores and safety actions for critical indicators (e.g. `apk_attachment`, `urgent_recovery`, `child_safety`).

2. **Privacy by Design (DPDP Act Aligned)**:
   - **Zero Device Scraping**: Web paste-only architecture; no access to device SMS, contacts, or call logs.
   - **Local Pre-LLM Masking**: Sensitive identifiers (`<PHONE_1>`, `<BANK_ACC_1>`, `<UPI_ID_1>`, `<EMAIL_1>`, `<OTP_1>`) are replaced with masked placeholders before any data reaches an LLM.
   - **Ephemeral Raw Vault**: Raw text is held in an in-memory vault strictly for the duration of analysis and deleted immediately upon assessment completion.
   - **Client Session Isolation & TTL**: Thread IDs are strictly validated, checkpoint writes are purged on session clear, and CORS origins are locked down to trusted hosts.

3. **Human-in-the-Loop (HITL) Interactive Interview**:
   - Ambiguous messages trigger targeted, low-friction follow-up questions rather than guessing.
   - Structured multi-question answering allows users to confirm critical context (e.g., whether they initiated a call or sent money), updating the assessment deterministically upon resume.

4. **Actionable Citizen Recovery Guidance**:
   - Direct integration with verified Indian cyber defense channels:
     - **DoT Chakshu Facility**: Direct reporting for suspected fraud calls, SMS, and WhatsApp (`https://sancharsaathi.gov.in/sfc`).
     - **National Cyber Crime Reporting Portal**: Suspect registry for malicious phone numbers, UPI IDs, and phishing URLs (`https://cybercrime.gov.in`).
     - **1930 Financial Fraud Helpline**: Rapid golden-hour reporting guidance to assist banks in placing liens when financial loss is reported.
     - **TRAI 1909**: DND and unsolicited commercial communications reporting.

---

## 🏗️ Multi-Agent Architecture

The core pipeline is orchestrated via a LangGraph state graph consisting of 9 specialized agents:

```
[Citizen Input]
       │
       ▼
 ┌─────────────┐
 │ IntakeAgent │ ── Local Regex PII Masking & Language Detection
 └─────────────┘
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
┌──────────────────┐           ┌───────────────────┐
│ ClassifierAgent  │           │  ThreatIntelAgent │
│ (Typology SC-01) │           │ (URL / TRAI DB)   │
└──────────────────┘           └───────────────────┘
       │                                 │
       └────────────────┬────────────────┘
                        ▼
               ┌─────────────────┐
               │ RiskScoreAgent  │ ── Deterministic Baseline + Safety Floors
               └─────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ InterviewAgent  │ ── Ambiguous? -> Pause & Ask User (HITL)
               └─────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ ExplainerAgent  │ ── Plain-English Behavioral Explanation
               └─────────────────┘
                        │
                        ▼
               ┌─────────────────┐
               │ AdviceEngine    │ ── Chakshu / 1930 / Safe Portal Advice
               └─────────────────┘
                        │
                        ▼
               ┌──────────────────┐
               │ GuardrailAgent   │ ── Language, Tone & Groundedness Checks
               └──────────────────┘
                        │
                        ▼
               ┌──────────────────┐
               │  FeedbackEngine  │ ── Session Cleanup & Feedback Audit
               └──────────────────┘
```

---

## 📊 Benchmark Evaluation (Phase 7 & Hardened Rigor)

Evaluated on the 50-case benchmark dataset across both English and Hinglish inputs:

| Evaluation Metric | Target | Baseline B0 (Rules) | Full Agentic (Ours) | Rigorous Verification |
| :--- | :---: | :---: | :---: | :--- |
| **Scam Recall (Warned > LOW)** | >= 95.0% | 44.4% | **97.2%** | Catches nuanced social engineering |
| **High-Risk Recall (HIGH/CRITICAL)** | >= 90.0% | 22.2% | **72.2%** | Correctly escalates active threats |
| **False Alarm Rate (Legit > LOW)** | <= 10.0% | 0.0% | **9.1%** | 0% on authenticated `.bank.in` & TRAI headers |
| **Required Safety Behaviors** | 100.0% | 97.7% | **95.5%** | 1930 recovery, 1098 child safety |
| **Typology Accuracy (Exact Top-1)** | >= 80.0% | N/A | **97.1%** | Exact primary typology classification |
| **Evidence-ID Grounding Rate** | 100.0% | N/A | **100.0%** | Runtime citation consistency against active catalogue (S#, I#, K#, C#) |
| **Non-Devanagari Script Compliance** | 100.0% | 100.0% | **100.0%** | Zero Devanagari script leakage in English responses (script-level audit) |
| **Official Reporting Guidance** | N/A | N/A | **97.2%** | Direct Chakshu & Cyber Crime Portal guidance |
| **Ambiguous Case Handling** | 100.0% | 0.0% | **66.7%** | Interactive interview triggered on ambiguous text |

---

## 🚀 Quick Start & Installation

### 1. Environment Setup

ScamSaathi requires Python 3.11+. We provide both a pinned `requirements.lock` (authoritative, verified) and a flexible `requirements.txt`:

```bash
# Clone the repository
git clone <repo-url>
cd scamsaathi

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install authoritative dependencies
pip install -r requirements.lock
# Or for standard installation:
pip install -e .
```

### 2. Configuration (`.env`)

Copy `.env.example` to `.env` and provide your API keys:

```bash
cp .env.example .env
```

Key configuration options (configured via `.env` or environment):
- `GEMINI_API_KEY`: Google Gemini API key (paid tier recommended).
- `GROQ_API_KEY`: Optional Groq API key for multi-provider fallback.
- `SCAMSAATHI_MODE`: Operating mode — `live` (calls model and caches), `cached` (reads cache only), or `offline` (deterministic fallback on cache miss).
- `GEMINI_MODEL_FAST`: Fast classification model (default: `gemini-3.5-flash-lite` from `config/llm.yaml`).
- `GEMINI_MODEL_REASONING`: Reasoning/explanation model (default: `gemini-3.8-flash` from `config/llm.yaml`).
- `SCAMSAATHI_MAX_LLM_CALLS_PER_REQUEST`: Per-request call budget cap (default: 6).

### 3. Running the Streamlit Web Application

```bash
streamlit run src/scamsaathi/ui/streamlit_app.py
```
Open your browser at `http://localhost:8501`.

### 4. Running the FastAPI REST Service

```bash
uvicorn scamsaathi.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API docs available at `http://localhost:8000/docs`.
- Features cryptographic session token ownership verification and automated 24-hour checkpoint TTL cleanup.

### 5. Running the Air-Gapped Offline Demo

Demonstrates multi-agent analysis on 15 canonical Indian scam scenarios without requiring live internet or API keys:

```bash
python scripts/run_agentic.py
```

### 6. Running the Benchmark Harness

```bash
python scripts/run_benchmarks.py
```

---

## 🧪 Testing & Verification

Run the full pytest suite (259 unit and integration tests):

```bash
pytest -v
```

All tests run completely offline and verify:
- Deterministic signal extractors and blocklist queries
- PII masking and raw vault clearing
- State graph routing and interrupt-resume cycles
- LLM Gateway caching, retries, and fallback circuit-breakers
- FastAPI endpoints, session ownership tokens, 24h TTL cleanup, CORS restrictions, and session deletion
- Advice engine contact allowlists and URL validation

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
├── reports/                # Benchmark evaluation reports & execution metadata
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
├── tests/                  # 259 unit and integration tests
├── pyproject.toml          # Project metadata & configuration
├── requirements.txt        # Pinned direct dependencies
├── requirements-dev.txt    # Development and test dependencies
└── requirements.lock       # Authoritative full environment lock
```

---

## 📜 License & Disclaimers

Developed as a Capstone Project for the Hero Vired Professional Certification in Agentic AI.
All rights reserved © 2026 Thiagarajan Baskarasubramanian.
