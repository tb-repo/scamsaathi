# 06. Tool Specifications and API Contracts

| Field | Value |
|---|---|
| Version | 1.0 (Approved) |
| Date | 2026-11-11 |

All tools are Python functions with Pydantic input/output models. Deterministic tools are pure where possible so they can be unit tested without network access.

## 1. Tool catalogue

| Tool | Type | Network | Used by | Requirements |
|---|---|---|---|---|
| `pii_masker` | Deterministic | No | A1, A9, LLM Gateway | FR-060 |
| `language_detector` | Deterministic (script and keyword heuristics), LLM fallback | No / LLM | A1 | FR-002 |
| `entity_extractor` | Deterministic (regex) | No | A2 | FR-010 |
| `url_analyzer` | Deterministic heuristics | No (WHOIS optional) | A3 | FR-021 |
| `reputation_lookup` | SQLite | No | A3 | FR-022 |
| `official_domain_check` | SQLite / fuzzy match | No | A3 | FR-024 |
| `external_reputation` | API (optional) | Yes | A3 | FR-023 |
| `kb_retriever` | Vector search | Local (embedding maybe API) | A4 | FR-020 |
| `risk_scorer` | Deterministic | No | A6 | FR-031, FR-032 |
| `advice_templates` | Curated data | No | A8 | FR-050 |
| `official_contacts` | Curated data | No | A8 | FR-051 |
| `report_generator` | Deterministic | No | A8 | FR-053 |
| `llm_gateway` | Provider client | Yes | LLM agents | FR-072 to FR-076 |
| `ocr_extract` (stretch) | OCR | Local/API | A1 | FR-005 |

## 2. Core data schemas

Shown as Python-style definitions; the implementation uses Pydantic v2.

```python
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

class Language(str, Enum):
    EN = "en"; HINGLISH = "hinglish"; HI = "hi"; OTHER = "other"

class InputMode(str, Enum):
    MESSAGE = "message"; SITUATION = "situation"; ENTITY_QUERY = "entity_query"

class Entity(BaseModel):
    kind: Literal["url", "phone", "upi", "email", "amount", "account_like", "id_number"]
    value_ref: str            # reference into the in-memory map, never the raw value
    masked: str               # e.g. "<PHONE_1>"
    span: tuple[int, int]

class Signal(BaseModel):
    name: str                 # from fixed vocabulary (doc 05, A2)
    confidence: float = Field(ge=0, le=1)
    evidence_span: str        # short quote from masked text
    evidence_id: str          # e.g. "S3"

class SignalSet(BaseModel):
    entities: list[Entity]
    signals: list[Signal]
    impersonated_org: Optional[str] = None

class IntelFinding(BaseModel):
    entity_ref: str
    check: str                # e.g. "blocklist", "lookalike_domain", "shortener"
    severity: Literal["info", "low", "medium", "high"]
    detail: str
    evidence_id: str          # e.g. "I2"

class IntelResult(BaseModel):
    findings: list[IntelFinding]
    degraded: bool = False

class TypologyMatch(BaseModel):
    code: str                 # e.g. "SC-02"
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[str]

class ClassificationResult(BaseModel):
    matches: list[TypologyMatch]
    needs_more_info: bool
    missing_facts: list[str]
    kb_chunk_ids: list[str]

class Contribution(BaseModel):
    factor: str
    points: float
    evidence_ids: list[str]

class RiskScore(BaseModel):
    value: int = Field(ge=0, le=100)
    level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    contributions: list[Contribution]
    overrides: list[str]
    llm_adjustment: int = 0
    llm_adjustment_reason: Optional[str] = None

class Reason(BaseModel):
    text: str
    evidence_ids: list[str]

class Explanation(BaseModel):
    headline: str
    reasons: list[Reason]
    uncertainty: str

class Action(BaseModel):
    priority: int
    text: str

class OfficialContact(BaseModel):
    name: str
    channel: str              # phone, url
    value: str
    verified_on: str          # ISO date

class AdviceBundle(BaseModel):
    actions: list[Action]
    contacts: list[OfficialContact]
    complaint_draft: Optional[str] = None
    urgent_recovery_mode: bool = False

class GuardrailResult(BaseModel):
    passed: bool
    failures: list[str]
```

## 3. Tool contracts

### 3.1 `pii_masker`

| Item | Detail |
|---|---|
| Signature | `mask(text: str) -> MaskResult` |
| Output | `masked_text`, `entities` (kind, placeholder, span), `map_ref` (in-memory reversible map) |
| Patterns | Indian mobile numbers (+91 and 10-digit starting 6 to 9), generic long digit runs (account/card), Aadhaar (12 digits, optional spacing), PAN (`AAAAA9999A`), email, UPI ID (`name@handle`), IFSC |
| Placeholders | `<PHONE_1>`, `<UPI_1>`, `<ACCT_1>`, `<ID_1>`, `<EMAIL_1>` |
| Notes | URLs are not masked by default (needed for analysis) but query strings containing tokens are stripped before any LLM call |
| Tests | Positive and negative cases, overlapping patterns, spaced digits, +91 forms, false positives on amounts |

### 3.2 `language_detector`

| Item | Detail |
|---|---|
| Signature | `detect(text: str) -> LanguageResult(language, confidence)` |
| Method | Script detection (Devanagari ratio), Hinglish keyword list (for example "aapka", "turant", "jaldi", "khata"), else English; LLM fallback when confidence is low |

### 3.3 `entity_extractor`

| Item | Detail |
|---|---|
| Signature | `extract(text: str) -> list[Entity]` |
| Entities | URLs (with and without scheme, shorteners), phone numbers, UPI IDs, emails, amounts (Rs., INR, rupee symbol, lakh/crore words), account-like numbers |
| Notes | Operates on text before masking inside the process; returns references, never logs raw values |

### 3.4 `url_analyzer`

| Item | Detail |
|---|---|
| Signature | `analyze(url: str, official_domains: list[str]) -> list[IntelFinding]` |
| Checks | Known shortener; IP-address host; punycode / mixed-script host; excessive subdomains; suspicious TLD list; brand-in-subdomain pattern (`sbi.secure-login.xyz`); edit-distance lookalike against official domains (Levenshtein / homoglyph map); `@` in URL; non-HTTPS with login keywords; blocklisted domain; official or legacy domain (mitigation); restricted suffix (`.bank.in`, `.gov.in`, `.nic.in`) |
| Claim checks (in `tools/intel.py`) | Message names an organisation but links elsewhere (`claimed_org_domain_mismatch`); message refers to a bank but the link is not `.bank.in` (`bank_claim_non_bank_domain`); message refers to a government body but the link is not `.gov.in`/`.nic.in` (`gov_claim_non_gov_domain`). Background: RBI required Indian banks to move to the exclusive `.bank.in` domain by 31 Oct 2025 (registrar IDRBT), verified on bank sites 2026-11-11 |
| Implemented | `src/scamsaathi/tools/url_analyzer.py`, `domains.py`, `intel.py` (2026-11-11) |
| Optional | WHOIS domain age (only when enabled; network dependent; failure is non-fatal) |
| Never | Fetches the URL content (avoids executing or visiting malicious sites) |

### 3.5 `reputation_lookup`

| Item | Detail |
|---|---|
| Signature | `lookup(kind, value) -> list[IntelFinding]` |
| Source | SQLite `blocklist` and `allowlist` tables (schema in doc 07) |
| Behaviour | Normalises phone (E.164) and UPI (lowercase) before lookup. Allowlist hit lowers severity and is reported as info |

### 3.6 `official_domain_check`

Checks whether a mentioned organisation and a domain/phone are consistent with the official data (doc 07). Returns mismatch findings, for example "message claims SBI but the link domain is not an SBI domain".

### 3.7 `external_reputation` (optional)

| Item | Detail |
|---|---|
| Candidates | Google Safe Browsing Lookup API, VirusTotal (free tier limits apply) |
| Status | Disabled by default; requires its own key and a data-sharing review (URLs are sent to a third party). Decision in a later ADR if enabled |

### 3.8 `kb_retriever`

| Item | Detail |
|---|---|
| Signature | `retrieve(query: str, k: int = 4, filters: dict | None = None) -> list[KBChunk]` |
| Query construction | Concatenate detected signal names, impersonated org, and a masked excerpt |
| Output | Chunk ID, typology code, text, source, last reviewed date, similarity score |
| Threshold | Minimum similarity configurable; below it returns empty (triggers signal-only fallback) |

### 3.9 `risk_scorer`

| Item | Detail |
|---|---|
| Signature | `score(signals, intel, classification, answers, config, llm_adjustment=None) -> RiskScore` |
| Formula | `raw = sum(weight[factor] * strength)` where strength is signal confidence or a severity multiplier; apply per-category caps to avoid double counting; clamp to 0 to 100 |
| Illustrative weights (tunable, not final) | credential_request 25, authority_impersonation 15, urgency 10, threat 15, payment_request 20, secrecy 15, app_install_request 20, link with lookalike/shortener 15, blocklist hit (override floor HIGH), reward_promise 10, advance_fee 15 |
| Combos | Bonus when high-risk combinations co-occur (for example credential_request + urgency + link) |
| Mitigations | Allowlist hit or verified official domain reduces points; none of these reduce below LOW if no signals |
| Overrides | Blocklist hit sets floor at HIGH. User confirms money sent or credentials shared sets `urgent_recovery_mode` and level at least HIGH |
| LLM adjustment | Optional, within +/- 10, requires reason, logged. Cannot cross an override floor |
| Thresholds (initial) | LOW 0 to 29, MEDIUM 30 to 59, HIGH 60 to 84, CRITICAL 85 to 100. Calibrated using the dev set in document 09 |
| Determinism | Pure function; identical inputs yield identical outputs |

### 3.10 `advice_templates` and `official_contacts`

Stored as YAML in `data/advice/` and `data/contacts/`. Each contact has `verified_on` and `source_url`. A test fails if any contact is older than the configured freshness window or lacks a source.

### 3.11 `report_generator`

| Item | Detail |
|---|---|
| Signature | `build(state, fmt="text"|"pdf") -> str | bytes` |
| Content | Date/time, scam type, masked summary of events, entities involved (masked unless user opts in to include), actions taken, checklist of details to keep (screenshots, transaction IDs) |
| PDF | Optional, uses a lightweight library; text format is the MVP |

### 3.12 `llm_gateway`

| Item | Detail |
|---|---|
| Signature | `generate(task: str, tier: Literal["fast","reasoning"], system: str, user: str, schema: type[BaseModel], temperature: float) -> BaseModel` |
| Guarantees | Schema-validated output, retries, cache, budget enforcement, PII assertion, telemetry |
| Errors | `BudgetExceeded`, `ProviderUnavailable`, `SchemaViolation`, `PIIDetectedInPrompt` |
| Config | `config/llm.yaml` maps tiers to provider/model, fallbacks, timeouts, cost table |

## 4. REST API contract

Base path `/api/v1`. All bodies are JSON. Responses include `request_id`.

### 4.1 `POST /analyze`

Request:
```json
{
  "text": "string, 1..4000 chars",
  "session_id": "optional string",
  "language_hint": "optional: en | hinglish | hi",
  "options": { "include_complaint_draft": false }
}
```

Response (final):
```json
{
  "request_id": "uuid",
  "session_id": "uuid",
  "status": "complete",
  "risk": { "level": "HIGH", "score": 78 },
  "scam_types": [ { "code": "SC-02", "name": "KYC / account block phishing", "confidence": 0.82 } ],
  "headline": "This looks like a KYC phishing attempt.",
  "reasons": [ { "text": "...", "evidence_ids": ["S1", "I1"] } ],
  "uncertainty": "string",
  "actions": [ { "priority": 1, "text": "Do not click the link." } ],
  "contacts": [ { "name": "National Cyber Crime Helpline", "channel": "phone", "value": "1930" } ],
  "degraded": false,
  "disclaimer": "string"
}
```

Response (needs follow-up):
```json
{
  "request_id": "uuid",
  "session_id": "uuid",
  "status": "needs_followup",
  "questions": [ { "id": "q1", "text": "Did they ask you to share an OTP?", "type": "yes_no" } ],
  "partial_risk": { "level": "MEDIUM", "score": 40 }
}
```

### 4.2 `POST /followup`

```json
{
  "session_id": "uuid",
  "answers": [ { "id": "q1", "answer": "yes" } ],
  "skip": false
}
```
Returns the same shape as `/analyze`.

### 4.3 `GET /health`

Returns service status, mode (`live`, `cached`, `offline`), KB version, and prompt versions. Does not expose keys.

### 4.4 `POST /feedback` (optional)

```json
{ "request_id": "uuid", "helpful": true, "was_scam": "yes|no|unsure" }
```

### 4.5 Errors

Standard error body `{ "error": { "code": "...", "message": "..." }, "request_id": "..." }`. Codes: `INVALID_INPUT` (400), `SESSION_NOT_FOUND` (404), `BUDGET_EXCEEDED` (429), `UPSTREAM_UNAVAILABLE` (503, returned as a degraded result where possible instead).

## 5. Configuration files

| File | Content |
|---|---|
| `config/llm.yaml` | Tier-to-model mapping, fallbacks, timeouts, cost table, call caps |
| `config/scoring.yaml` | Weights, caps, combos, thresholds |
| `config/routing.yaml` | Confidence thresholds, follow-up limits |
| `config/guardrails.yaml` | Banned phrases, PII patterns, disclaimer text |
