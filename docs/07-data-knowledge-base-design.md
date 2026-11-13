# 07. Data and Knowledge Base Design

| Field | Value |
|---|---|
| Version | 0.1 (Draft) |
| Date | 2026-11-11 |

## 1. Data principles

1. **Synthetic or public only.** No real victim data. Real-looking examples are written by the author or generated, then reviewed.
2. **Provenance.** Every KB entry and dataset record carries a source, author, and last-reviewed date.
3. **Reviewable files.** Data is stored as YAML/JSON/CSV in `data/` so changes are visible in version control.
4. **Rebuildable.** The vector index and SQLite databases are built from these files by scripts.

## 2. Folder layout

```
data/
  kb/
    typologies/        one YAML per scam typology (SC-01 .. SC-12)
    advisories/        short official-advice summaries (paraphrased, with source URL)
  intel/
    blocklist.csv      synthetic and curated bad indicators
    allowlist.csv      known-good indicators
    official_domains.csv   organisation to official domains / phones
    shorteners.txt     known URL shorteners
    suspicious_tlds.txt
  advice/              per-typology action templates (YAML)
  contacts/            verified official channels (YAML, with verified_on and source_url)
  eval/
    dev.jsonl          development set for tuning
    test.jsonl         held-out test set (not used for tuning)
    SCHEMA.md
  demo/                curated demo scenarios
```

## 3. Knowledge base: typology entry schema

```yaml
code: SC-02
name: KYC / account block phishing
version: 1
last_reviewed: 2026-11-11
summary: >
  Messages claiming the user's bank or wallet account will be blocked unless KYC is updated
  through a link or app.
how_it_works:
  - Scammer sends SMS/WhatsApp impersonating a bank.
  - Message creates urgency and includes a link or phone number.
  - Fake page collects card details, net banking credentials, or OTP.
red_flags:
  - Account will be blocked today
  - Link not on the bank's official domain
  - Asks for OTP, PIN, or card details
  - Asks to install an app
legit_contrast:
  - Banks do not ask for OTP, PIN or CVV by call, SMS, or link.
typical_signals: [urgency, authority_impersonation, credential_request, link_present]
example_phrases_en:
  - "Your account will be blocked. Update KYC now."
example_phrases_hinglish:
  - "Aapka khata band ho jayega, abhi KYC update karein."
recommended_actions:
  - Do not click the link or share OTP.
  - Contact the bank using the number on your card or official app.
sources:
  - title: <official advisory title>
    url: <verify and add>
```

Entries are written in the author's own words from official public guidance (RBI, NPCI, Indian Cyber Crime Coordination Centre, bank advisories). Do not copy long passages. URLs and wording must be verified before release (risk R-009).

## 4. Chunking and indexing

| Item | Decision |
|---|---|
| Chunk unit | One chunk per typology section: summary, how it works, red flags, contrast, examples, actions |
| Metadata | typology code, section, language, last_reviewed, source |
| Embedding | Gemini embeddings when a key is set (ADR-004, revised). Hinglish example phrases are separate chunks to improve recall |
| Index | BM25 built in memory at start-up; dense vectors cached as JSON in `.cache/kb/` keyed by KB version and model. No vector database (ADR-004) |
| Retrieval | top-k = 4, BM25 minimum score 0.5, RRF fusion (k=60), optional filter by typology code. Config in `config/kb.yaml` |
| Implemented | `src/scamsaathi/kb/` (store, retrieval, advice, factory), `scripts/build_kb.py`, `scripts/eval_retrieval.py`, eval queries in `data/kb/retrieval_eval.jsonl` (2026-11-11) |
| Sources | `data/kb/sources.yaml` register; each source records type (primary/secondary) and how it was checked. Six sources are `snippet_only` and must be read in full before release (R-009) |
| Versioning | KB version hash stored and reported by `/health` |

## 5. Intelligence database (SQLite `intel.db`)

```sql
CREATE TABLE blocklist (
  id INTEGER PRIMARY KEY,
  kind TEXT CHECK(kind IN ('phone','upi','domain','url')) NOT NULL,
  value_norm TEXT NOT NULL,
  category TEXT,           -- typology code
  source TEXT NOT NULL,    -- 'synthetic' or public source name
  added_on TEXT NOT NULL,
  UNIQUE(kind, value_norm)
);

CREATE TABLE allowlist (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  org TEXT,
  source TEXT NOT NULL,
  UNIQUE(kind, value_norm)
);

CREATE TABLE official_domains (
  id INTEGER PRIMARY KEY,
  org TEXT NOT NULL,       -- e.g. 'State Bank of India'
  org_type TEXT NOT NULL,  -- bank, government, regulator, payments
  domain TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,    -- verified | legacy (redirects to official) | unverified
  verified_on TEXT,        -- NULL only while status = 'unverified'
  source_url TEXT NOT NULL,
  brand_tokens TEXT NOT NULL  -- '|'-separated names used to detect impersonation
);
-- As implemented in src/scamsaathi/tools/intel_db.py (2026-11-11). status and
-- brand_tokens were added during Phase 2; unverified rows must be verified before release (R-009).
```

Seed data for the prototype is **synthetic** (for example reserved example domains and fictional numbers) so that the demo never accuses a real person or business. Real public indicators may be added only with a documented public source.

## 6. Session store (SQLite `sessions.db`)

| Table | Fields | Notes |
|---|---|---|
| `checkpoints` | thread_id, state_json (masked only), updated_at | LangGraph checkpointer; TTL 24 h cleaned on startup |
| `feedback` | request_id, helpful, was_scam, created_at | No text stored |

## 7. Evaluation dataset

### 7.1 Record schema

```json
{
  "id": "T-0001",
  "text": "synthetic message or situation",
  "language": "en|hinglish|hi",
  "label": "scam|legit|ambiguous",
  "typologies": ["SC-02"],
  "required": ["report_channel"],
  "must_have_signals": ["credential_request", "urgency"],
  "notes": "why this case exists",
  "split": "dev|test"
}
```

**Labels describe facts, not risk levels (decision 2026-11-13).** A risk level is ScamSaathi's own way of telling users how worried to be; nothing in reality has one. Cases are therefore labelled with what can be true of the case:

- `label`: `scam`, `legit`, or `ambiguous` (not enough information to tell).
- `typologies`: acceptable top scam types for a scam.
- `required`: behaviours that must happen whatever the score:
  - `report_channel`: an official reporting step in the top 3 actions;
  - `urgent_recovery`: 1930 first when money or secrets were lost;
  - `child_safety_path`;
  - `spam_1909`;
  - `no_designated_label`;
  - `no_questions` for a complete genuine message.

The core outcome follows from the label: a scam must be warned about (level above LOW), a genuine message must not raise an alarm (LOW), and an ambiguous case must lead to questions. The earlier `expected_level_min` / `expected_level_max` fields are dropped. Levels are reported, and their thresholds tuned on the dev split, but they are not pass or fail criteria. Checks are implemented once in `src/scamsaathi/evaluation/labels.py` and shared by tests and scripts.

Limitation: for synthetic cases the author asserts the label. Cases are built from documented scam patterns (RBI, I4C, DoT advisories), and an independent review of labels is planned before the test split is frozen.

### 7.2 Composition targets (initial)

| Category | Target count | Notes |
|---|---|---|
| Scam, clear | 60 | Spread across SC-01 to SC-12 |
| Scam, subtle | 20 | Fewer red flags |
| Legitimate (hard negatives) | 50 | Real-looking bank alerts, OTP notices, delivery updates, promotional offers |
| Ambiguous (needs interview) | 20 | Short or vague descriptions |
| Adversarial | 15 | Prompt injection, obfuscated text, mixed language, typos |

Total about 165. Split roughly 40% dev, 60% test. Counts are targets, adjustable (decision logged). The test split is frozen before the first full evaluation and never used for tuning.

### 7.3 Creation process

1. Write seeds per typology based on the KB.
2. Use the LLM to produce variations (English, Hinglish) from synthetic seeds only. Review manually.
3. Include legitimate messages that share surface features with scams (for example genuine OTP delivery message that says "do not share").
4. Record generation method and review status per record.
5. Optional: add public datasets (for example public SMS spam corpora) after checking licence and suitability for Indian scam patterns. Document the licence in `data/eval/SCHEMA.md`.

## 8. Data lifecycle

| Data | Retention | Notes |
|---|---|---|
| User input | Not stored | In memory during request only |
| Masked text in checkpoints | 24 h | Needed for interview resume |
| LLM cache | Until manually cleared | Contains masked prompts and responses only; excludes live user traffic by default (cache only for demo and eval runs, configurable) |
| Logs | Rolling, 7 days | No raw PII; masked text excerpts limited length |
| Feedback | Until project ends | No raw text |

## 9. Data quality checks

- Schema validation of all YAML/JSON on build.
- Duplicate detection in the eval set.
- Link and source verification checklist before final submission.
- Contact freshness test (see doc 06, 3.10).
