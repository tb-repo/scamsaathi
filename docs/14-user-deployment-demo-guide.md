# 14. User, Deployment and Demo Guide

| Field | Value |
|---|---|
| Version | 0.1 (Draft; commands finalised during P1 and P8) |
| Date | 2026-11-11 |

Commands below describe the intended setup for Windows PowerShell. They are provisional until the scaffold exists and must be re-verified when written.

## 1. Prerequisites

- Windows, Python 3.11 or newer (verify with `python --version`).
- Git.
- A Gemini API key for the project (Google AI Studio) with billing set up.
- Internet access for live mode.

## 2. Setup (planned)

```powershell
# from the project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # verified 2026-11-11 on Python 3.13.14
python -m pytest                      # unit tests (no network, no API key needed)
python -m mypy                        # strict type check
Copy-Item .env.example .env
# edit .env: set GEMINI_API_KEY and model IDs (never commit .env)
python scripts/build_kb.py        # builds vector index and intel.db from data/
```

## 3. Run (planned)

```powershell
uvicorn scamsaathi.api.main:app --reload     # API on http://127.0.0.1:8000
streamlit run src/scamsaathi/ui/app.py       # UI
```

Modes (set `SCAMSAATHI_MODE` in `.env`):

| Mode | Behaviour | Use |
|---|---|---|
| `live` | Calls Gemini, writes cache | Development, evaluation pilot |
| `cached` | Reads cache, fails on miss | Reproducible evaluation |
| `offline` | Cache plus deterministic only | Demo without network |

## 4. Using ScamSaathi

1. Paste the message, or describe the call in your own words (English or Hinglish).
2. Do not include your own name, full account numbers, or OTPs. Use synthetic text for the demo.
3. Read the risk level, reasons, and next steps.
4. If asked follow-up questions, answer briefly or choose "Skip".
5. Use the official channels listed (for example the National Cyber Crime Helpline 1930 and cybercrime.gov.in) to report. Contact details are verified against the list in `data/contacts/` and carry a verification date.

## 5. Troubleshooting (to be extended)

| Symptom | Likely cause | Action |
|---|---|---|
| 429 or "prepayment credits depleted" | Quota or billing balance or sync delay | Check billing, top up small amount, wait for sync, switch to cached mode |
| Empty KB results | Index not built | Run `build_kb.py` |
| Answers marked degraded | LLM unavailable | Check key, network, mode |
| Port in use | Another process | Change port |

## 6. Demo plan (10 minutes)

| Min | Segment | Content |
|---|---|---|
| 0 to 1 | Problem | Why scams succeed (urgency, impersonation) |
| 1 to 2 | Architecture | Show agent graph diagram (Mermaid export) |
| 2 to 4 | Scenario 1 | KYC phishing SMS (English): signals, intel, HIGH, actions |
| 4 to 5 | Scenario 2 | Hinglish digital-arrest style call description: CRITICAL, 1930 |
| 5 to 7 | Scenario 3 | Vague parcel call: interview agent asks questions, then result |
| 7 to 8 | Scenario 4 | Legitimate bank OTP notice: low risk, no false alarm |
| 8 to 9 | Safety | Injection attempt blocked; PII masking view; degraded mode |
| 9 to 10 | Results | Evaluation numbers vs baselines; cost per request |

Backup: run in `offline` mode with the pre-recorded cache; keep a screen recording.

Demo scenarios are stored in `data/demo/` (synthetic only).

## 7. Deployment options (decision deferred)

| Option | Notes |
|---|---|
| Local demo | Default; no hosting cost |
| Free-tier cloud host | Optional shareable link; secrets via host env vars; check data and cost implications; consider rate limiting |

## 8. Release checklist

- [ ] All MUST requirements implemented and traced
- [ ] Tests pass; evaluation report archived
- [ ] Secret scan clean, `.env` not in history
- [ ] Contacts and sources re-verified (dates updated)
- [ ] Demo rehearsed in all three modes
- [ ] README and docs updated; CHANGELOG tagged
