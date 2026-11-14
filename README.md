# ScamSaathi (स्कैम साथी)

**An Agentic AI Assistant for Mobile Scam Defense in India.**

> *Helping citizens identify mobile scams, understand social engineering manipulation, and take safe, official recovery steps before or after financial loss.*

---

| Attribute | Details |
| :--- | :--- |
| **Certification** | Hero Vired — Professional Certification in Agentic AI (Capstone Project) |
| **Author** | Thiagarajan Baskarasubramanian |
| **Architecture** | 9-Agent StateGraph with LangGraph & SQLite Checkpointer |
| **Primary LLMs** | Google Gemini (gemini-2.5-flash / gemini-2.5-pro) |
| **Fallback LLMs** | Groq (llama-3.3-70b-versatile) with Circuit-Breaker Gateway |
| **Scope** | Mobile SMS, WhatsApp, and call transcripts in English & Hinglish |
| **Test Suite** | 248 Unit & Integration Tests (100% Passing) |
| **Evaluation** | 50-Case Comprehensive Benchmark (97.2% Scam Recall, 0% False Alarms on Banking) |

> ⚠️ **Important Safety Disclaimer**: ScamSaathi provides risk assessments and safety guidance, not legal advice or definitive investigative verdicts. Automated masking protects phone numbers, accounts, UPI IDs, and OTPs, but pattern matching cannot reliably redact personal names or street addresses. Always verify independently through official channels.

---

## 🌟 Key Capabilities

1. **Deterministic-First Agentic Defense**:
   - **Deterministic Rules & Threat Intel**: URL blocklists, TRAI designated service series (1600/1601), `.bank.in` / `.gov.in` domain legitimacy verification, and keyword signal extraction run deterministically before LLM invocation.
   - **Bounded LLM Reasoning**: LLMs classify Indian cyber fraud typologies (I4C SC-01 through SC-10) and explain social engineering tactics within bounded score delta limits.
   - **Deterministic Safety Floors**: Overrides enforce strict minimum risk scores and safety actions for critical indicators (e.g. `apk_attachment`, `urgent_recovery`, `child_safety`).

2. **Privacy by Design (DPDP Act Aligned)**:
   - **Zero Device Scraping**: Web paste-only architecture; no access to device SMS, contacts, or call logs.
   - **Local Pre-LLM Masking**: Sensitive identifiers (`<PHONE_1>`, `<BANK_ACC_1>`, `<UPI_ID_1>`, `<OTP_1>`) are replaced with masked placeholders before any data reaches an LLM.
   - **Ephemeral Raw Vault**: Raw text is held in an in-memory vault strictly for the duration of analysis and deleted immediately upon assessment completion.
   - **Client Session Isolation & TTL**: Thread IDs are strictly validated, checkpoint writes are purged on session clear, and CORS origins are locked down to trusted hosts.

3. **Human-in-the-Loop (HITL) Interactive Interview**:
   - Ambiguous messages trigger targeted, low-friction follow-up questions rather than guessing.
   - Structured multi-question answering allows users to confirm critical context (e.g., whether they initiated a call or sent money), updating the assessment deterministically upon resume.

4. **Actionable Citizen Recovery Guidance**:
   - Direct integration with verified Indian cyber defense channels:
     - **DoT Chakshu Facility**: Direct reporting for suspected fraud calls, SMS, and WhatsApp (`https://sancharsaathi.gov.in/sfc`).
     - **National Cyber Crime Reporting Portal**: Suspect registry for malicious phone numbers, UPI IDs, and phishing URLs (`https://cybercrime.gov.in`).
     - **1930 Financial Fraud Helpline**: Immediate golden-hour lien request guidance when financial loss is reported.
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
| **Reason Groundedness** | 100.0% | N/A | **100.0%** | 100% cited evidence IDs exist in signals/intel |
| **English Language Compliance** | 100.0% | 100.0% | **100.0%** | Zero Devanagari script leakage in advice |
| **Official Reporting Guidance** | N/A | N/A | **94.4%** | Direct Chakshu & Cyber Crime Portal guidance |
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

Key configuration options:
- `SCAMSAATHI_GEMINI_API_KEY`: Google Gemini API key.
- `SCAMSAATHI_GROQ_API_KEY`: Groq fallback key (optional).
- `SCAMSAATHI_MODE`: `development`, `production`, or `offline_demo`.
- `SCAMSAATHI_PRIMARY_MODEL_FAST`: `gemini-2.5-flash`

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

Run the full pytest suite (248 unit and integration tests):

```bash
pytest -v
```

All tests run completely offline and verify:
- Deterministic signal extractors and blocklist queries
- PII masking and raw vault clearing
- State graph routing and interrupt-resume cycles
- LLM Gateway caching, retries, and fallback circuit-breakers
- FastAPI endpoints, CORS restrictions, and session deletion
- Advice engine contact allowlists and URL validation

---

## 📁 Repository Structure

```
scamsaathi/
├── data/
│   ├── advice/             # Canonical advice templates (advice.yaml)
│   ├── blocklists/         # Malicious domains, hashes, and handles
│   ├── contacts/           # Verified official Indian reporting channels
│   ├── evaluation/         # 50-case benchmark evaluation dataset
│   └── knowledge_base/     # Indian cyber fraud typologies (SC-01 to SC-10)
├── docs/                   # Full project documentation & architectural decisions
├── reports/                # Benchmark evaluation reports & execution metadata
├── scripts/
│   ├── run_agentic.py      # Air-gapped offline interactive demo
│   └── run_benchmarks.py   # Comprehensive benchmarking harness
├── src/scamsaathi/
│   ├── agents/             # 9 specialized LangGraph agents
│   ├── api/                # FastAPI application & Pydantic schemas
│   ├── core/               # PII vault, masking, gateway & circuit breaker
│   ├── pipeline/           # AgentRunner & Baseline B0 pipeline
│   ├── tools/              # Threat intel DB & blocklist engines
│   └── ui/                 # Streamlit web user interface
├── tests/                  # 248 unit and integration tests
├── pyproject.toml          # Project metadata & configuration
├── requirements.txt        # Package requirements
└── requirements.lock       # Authoritative locked dependencies
```

---

## 📜 License & Disclaimers

Developed as a Capstone Project for the Hero Vired Professional Certification in Agentic AI.
All rights reserved © 2026 Thiagarajan Baskarasubramanian.
