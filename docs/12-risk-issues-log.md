# 12. Risk, Issues, Assumptions and Open Questions Log

| Field | Value |
|---|---|
| Version | 0.1 |
| Last updated | 2026-11-11 |

Scales: Likelihood (L) and Impact (I) are Low / Medium / High. Status: Open, Mitigating, Closed, Realised.

## 1. Risk register

| ID | Risk | L | I | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R-001 | False negatives give false reassurance | M | H | Never output "safe"; recall-focused evaluation; blocklist and signal overrides; disclaimers | Author | Open |
| R-002 | False positives alarm users or defame legitimate organisations | M | M | Hard-negative test cases; reasons shown; wording avoids accusation | Author | Open |
| R-003 | Gemini quota or rate limits interrupt demo | M | H | Paid tier, retries, cache, offline mode, optional fallback provider | Author | Open |
| R-004 | Credit usage order differs from expectation (promotional vs prepaid) or credits do not cover Gemini API | M | M | Verify with small calls and billing credit summary after first calls; budget alert; keep prepaid balance above zero | Author | Open |
| R-005 | Cost overrun during evaluation | M | M | Pilot of 10 cases, cache, estimate before run, 25% rule (doc 10) | Author | Open |
| R-006 | PII leakage to LLM, logs, or cache | L | H | Masking, gateway assertion, log audit tests, synthetic data only (ADR-007) | Author | Open |
| R-007 | API key exposure | L | H | `.env` ignored, secret scan, key restrictions, budget alert | Author | Open |
| R-008 | Hinglish quality weaker than English | M | M | Per-language evaluation, Hinglish few-shots and KB examples, keyword-based signals | Author | Open |
| R-009 | Outdated or incorrect official contacts and advisories | M | H | Verify against official sources, store `verified_on` and `source_url`, freshness test. Partly realised 2026-11-11: banks had moved to `.bank.in`, so remembered domains (sbi.co.in, hdfcbank.com) were out of date; caught by live verification and kept as `legacy`. NPCI and cybercrime.gov.in still `unverified` | Author | Mitigating |
| R-010 | Schedule slip (single developer, deadline unknown) | H | M | MVP-first scope, stretch list, weekly review, de-scope plan below | Author | Open |
| R-011 | Framework or library API changes break code | M | M | Pin versions, spike early, minimal framework surface in nodes | Author | Open |
| R-012 | Dataset too small or synthetic bias inflates metrics | H | M | Hard negatives, adversarial cases, frozen test split, honest limitations | Author | Open |
| R-013 | Prompt injection manipulates output | M | H | Scorer decides level, guardrails, injection test corpus | Author | Open |
| R-014 | Course requires a different framework | L | H | Resolve Q-1 early; design keeps node logic framework-independent | Author | Open |
| R-015 | Model deprecations or renamed model IDs | M | L | Models in config, health endpoint reports models | Author | Open |
| R-016 | Over-claiming accuracy in the final report | M | M | Report actual numbers with confidence caveats and error analysis | Author | Open |
| R-017 | Labelling a designated-series number (140xx, 1600xx, 1601xx) or a government communication as scam or spam conflicts with TRAI TCCCPR Regulation 34A | M | M | ADR-009: never tag these series (FR-081) or DLT headers (FR-086); no in-app spam reporting (FR-087). Regulation 34A read in full on 2026-11-13; it covers "call management applications or similar services" (doc 16 section 12.2) | Author | Closed 2026-11-13 |
| R-018 | App output read as legal advice (sections, punishments) | L | M | FR-083: facts-only complaint drafts, no sections or punishments in assessments | Author | Mitigating |
| R-019 | Unverified punishment figures quoted in the final report | M | L | Doc 16 marks each figure's source. 2026-11-12: BNS 318/319/204/308/336/351, IT Act 66C/66D/66E, Telecom Act 42, Online Gaming Act s.9, POCSO, DPDP Schedule verified from the official PDFs. Remaining unverified: IT Act 66 (secondary), TCCCPR 34A | Author | Mitigating |
| R-020 | Child-safety screen misses a case (false negative) or over-triggers | M | H | Needs both a minor and a sexual-content indicator; deliberately broad wording; CRITICAL floor and police-first advice; add cases to the evaluation set (docs/09) | Author | Open |
| R-021 | New signals (sextortion, mule, money game) raise false positives on everyday text | M | M | Patterns require sensitive or money context; negative tests for everyday phrases; dev-set tuning | Author | Open |

### De-scope order if time is short
1. Drop stretch items (OCR, Devanagari, voice).
2. Drop PDF report (keep text).
3. Drop external reputation and optional fallback provider.
4. Reduce evaluation baselines to B0, B1, Full.
5. Reduce typologies from 12 to the 6 most common (SC-01, SC-02, SC-03, SC-04, SC-05, SC-07).

## 2. Issues log

| ID | Date | Issue | Impact | Resolution | Status |
|---|---|---|---|---|---|
| I-001 | 2026-11-11 | Python is not usable on the laptop: `python.exe` resolves only to the Microsoft Store placeholder (version 0.0.0.0) and the `py` launcher is not found. The shell also runs in a restricted language mode, which suggests a managed device | Blocks Phase 1 and all code execution | Author installed Python 3.13.14 (Microsoft Store build); verified in the project shell | Closed 2026-11-11 |
| I-002 | 2026-11-11 | Device Application Control policy blocks the `ruff` native binary (WinError 4551) | No automated linting or formatting; style issues may go unnoticed | `mypy --strict` (pure Python) still runs and passes. Options: ask IT to allow ruff, run ruff in CI (for example GitHub Actions) once the repo is pushed, or use a pure-Python linter. Decision pending with author | Open |
| I-003 | 2026-11-11 | Project, including `.venv`, is inside a OneDrive-synced folder | OneDrive syncs thousands of venv files; may slow installs or lock files; the first install appeared to stall | Option: keep source in OneDrive but create the venv outside it (for example `C:\Users\<user>\venvs\scamsaathi`). `.venv` is already git-ignored. Decision pending with author | Open |

Template: ID, date found, description, impact, root cause, resolution, date closed, lessons.

## 3. Assumptions

| ID | Assumption | Validate by | Status |
|---|---|---|---|
| A-1 | Gemini paid tier is active with credit for development and evaluation | First live call and billing check | To validate |
| A-2 | Local LLMs are not used (16 GB RAM, no GPU) | n/a | Confirmed by author |
| A-3 | Only synthetic or public data is used | Dataset review | Policy |
| A-4 | Course does not mandate another framework | Q-1 | To validate |
| A-5 | India-specific scope | Author confirmation | Assumed |
| A-6 | Python 3.11+ can be installed on the laptop | Environment check in P1 | Confirmed: Python 3.13.14 (I-001 closed) |
| A-7 | Eligible promotional credits apply to Gemini API usage | Billing credit summary | To validate |

## 4. Open questions

| ID | Question | Needed by | Owner | Status |
|---|---|---|---|---|
| Q-1 | Does the certification mandate a specific framework or deliverable format? | Before P1 | Author | Open |
| Q-2 | What are the submission deadline and demo format (live, recorded, presentation)? | Before P1 | Author | Open |
| Q-3 | Which Gemini model IDs, rate limits, and prices are shown in AI Studio for this project? | P1 | Author | Partly resolved 2026-11-11: models and prices taken from official docs (ADR-008); author to confirm the project's rate limits in AI Studio |
| Q-4 | Exact usable credit: do the promotional credits cover Gemini API, expiry date, terms? | P1 | Author | Open |
| Q-5 | Which cited statistics (for example reported cyber fraud numbers) will the business case use? | P9 | Author with Kiro | Open |
| Q-6 | Is the India-specific scope confirmed, including helplines? | Before P3 | Author | Open |
| Q-7 | Is a public hosted demo required, or is local demo enough? | P8 | Author | Open |
| Q-8 | Does the paid Gemini API data-use policy permit the intended handling of masked synthetic prompts? | P1 | Author with Kiro | Open |
| Q-9 | Where is the "I4C Acts and Rules Portal" referenced in the author's brief? (Not found in research; `docs/IndianOfficialWebSites/Websites.md` was empty on 2026-11-12) | P9 | Author | Open |
| Q-10 | Any DPDP section 16 notification restricting transfer to the country where Gemini processes data? | Before any real-user use | Author with Kiro | Open |
| Q-11 | Do the IT Intermediary Rules 2021 or CERT-In directions apply to a public deployment of ScamSaathi? | P8 (if deployed) | Author | Open |

## 5. Challenges anticipated (to be updated with actuals)

| Challenge | Notes |
|---|---|
| Hinglish understanding and spelling variation | Mix of keyword lists, LLM extraction, and few-shots |
| Balancing alarm vs reassurance wording | Wording review in manual checklist |
| Keeping the LLM from overriding deterministic logic | Gateway-enforced schemas and bounded adjustments |
| Creating a realistic but synthetic dataset | Seeds from KB, variations, hard negatives |
| Evaluating explanation quality | Mixed automatic groundedness and manual sampling |
