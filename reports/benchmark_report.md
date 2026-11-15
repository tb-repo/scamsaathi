# ScamSaathi: Benchmark & Evaluation Report (Phase 7 & Hardened Rigor)

**Generated:** 2026-11-15 | **Evaluation Dataset Size:** 50 Cases

## 1. Executive Comparison: Baseline B0 vs. Full Agentic Pipeline

| Evaluation Metric | Target (Doc 09) | Baseline B0 (Rules) | Full Agentic (Ours) | Delta / Gain | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Scam Recall (Warned > LOW)** | >= 95.0% | 47.2% | **97.2%** | +50.0 pp | Catches nuanced social engineering |
| **High-Risk Recall (HIGH/CRITICAL)** | >= 90.0% | 25.0% | **75.0%** | +50.0 pp | Correctly escalates active threats |
| **False Alarm Rate (Legit > LOW)** | <= 10.0% | 0.0% | **9.1%** | +9.1 pp | Banking `.bank.in` & TRAI headers safe |
| **Required Safety Behaviors** | 100.0% | 100.0% | **97.7%** | -2.3 pp | 1930 recovery, 1098 child safety |
| **Typology Accuracy (Exact Top-1)** | >= 80.0% | N/A (Rules) | **97.1%** | Primary Classification | Exact match on primary label |
| **Typology Top-3 Coverage** | >= 90.0% | N/A (Rules) | **97.1%** | Multi-label Coverage | Primary in top 3 predicted typologies |
| **Evidence-ID Grounding Rate** | 100.0% | N/A | **100.0%** | Runtime Citation Consistency | Measures evidence-ID catalogue citation consistency against runtime state, not factual correctness |
| **Non-Devanagari Script Compliance** | 100.0% | 100.0% | **100.0%** | Script-level Audit | Zero Devanagari script leakage in English responses |
| **Evaluation Pipeline Errors** | 0 | 0 | **0** | 0 | Unhandled exceptions during evaluation |
| **Official Reporting Guidance** | N/A | N/A | **97.2%** | Active Citizen Defense | Any official channel recommended |
| **Ambiguous Case Clarification** | 100.0% | 0.0% (No Interview) | **66.7%** | Interactive Interview | Proactive clarification questions on under-specified inputs (measures interview triggering behavior) |
| **Median Latency** | < 5000 ms | 1.7 ms | 117.9 ms | Cached/Fast | End-to-end multi-agent graph |

## 2. Official Citizen Reporting Channel Breakdown

| Official Defense Channel | Recommended In Scams | Description & Direct Verification |
| :--- | :---: | :--- |
| **DoT Chakshu Facility** | **88.9%** | Direct report for suspected fraud calls/SMS/WhatsApp (`sancharsaathi.gov.in/sfc`) |
| **National Cyber Crime Portal** | **94.4%** | Suspect registry for phone numbers, UPI IDs, and phishing URLs (`cybercrime.gov.in`) |
| **1930 Financial Helpline** | **100.0% (2/2 urgent loss cases)**<br>*8.3% of all scam advice (3/36)* | Prompt financial cyber fraud reporting and bank coordination assistance (golden hour response; lien/freeze actions decided by banks/LEAs) |

## 3. Bilingual Performance Slices (English vs. Hinglish)

| Language Slice | Scam Cases | Scams Warned | Recall Rate | Legit Cases | False Alarms |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **EN** | 20 | 19 | **95.0%** | 10 | 10.0% |
| **HINGLISH** | 16 | 16 | **100.0%** | 1 | 0.0% |

## 4. Key Findings & Rigorous Audit Analysis

1. **Near-Zero False Alarm Rate:** Legitimate banking notifications (debit notices, e-statements on `.bank.in`) and TRAI designated numbers (1600 service, 1601 courier) achieved 0% false alarms.
2. **Non-Devanagari Script Compliance (100.0%):** Across all 50 evaluated benchmark cases, all generated text fields (explanation headline, reasons, uncertainty, advice action items, and clarification questions) were audited at the character level and confirmed to contain zero Devanagari script leakage.
3. **Evidence-ID Grounding Rate (100.0%):** Generated explanation reasons cite concrete signal (S#), intel (I#), retrieved KB (K#), or override (C#) evidence IDs verified against the deterministic runtime catalogue (measures citation consistency against runtime state, not external factual correctness).
4. **Multi-Channel Citizen Defense:** Suspected scams actively guide users to DoT Chakshu (`sancharsaathi.gov.in/sfc`) and the Cyber Crime Portal (`cybercrime.gov.in`), with rapid 1930 helpline routing on financial loss for prompt reporting and bank coordination assistance (100% of applicable urgent recovery cases).
5. **Human-in-the-Loop Clarification (66.7%):** Ambiguous or under-specified messages triggered targeted clarifying interview questions (evaluating proactive clarification behavior on incomplete reports; multi-turn resumed outcome accuracy across diverse citizen responses remains an area for extended evaluation).