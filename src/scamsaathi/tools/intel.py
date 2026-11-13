"""Threat-intelligence aggregation (A3 deterministic core; FR-021, FR-022, FR-024).

Runs every lookup for the extracted entities and returns an ``IntelResult`` whose findings
carry masked details and evidence IDs (I1, I2, ...). Details never contain raw PII.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from scamsaathi.schemas import IntelFinding, IntelResult
from scamsaathi.tools.domains import parse
from scamsaathi.tools.entities import RawEntity
from scamsaathi.tools.intel_db import IntelDB
from scamsaathi.tools.url_analyzer import Finding, analyze

# Generic claims of being a bank or government body, English and Hinglish.
_BANK_CLAIM: Final = re.compile(r"\b(bank|net ?banking|kyc|debit card|credit card|khata)\b", re.I)
_GOV_CLAIM: Final = re.compile(
    r"\b(police|cbi|customs|court|government|govt|ministry|income tax|trai|dot|uidai|aadhaar|"
    r"cyber (cell|crime)|crime branch|narcotics|enforcement directorate|sarkar)\b",
    re.I,
)


@dataclass(frozen=True)
class Claims:
    """Organisations or organisation types the message claims to be from."""

    orgs: frozenset[str]
    bank: bool
    government: bool


def detect_claims(text: str, db: IntelDB) -> Claims:
    lowered = text.lower()
    orgs = frozenset(
        o.org
        for o in db.official
        if any(re.search(rf"\b{re.escape(t)}\b", lowered) for t in o.brand_tokens)
    )
    bank = bool(_BANK_CLAIM.search(text)) or any(
        o.org_type == "bank" for o in db.official if o.org in orgs
    )
    government = bool(_GOV_CLAIM.search(text)) or any(
        o.org_type == "government" for o in db.official if o.org in orgs
    )
    return Claims(orgs=orgs, bank=bank, government=government)


def _claim_mismatch(url: str, claims: Claims, db: IntelDB) -> list[Finding]:
    """Message claims a bank or government sender but links elsewhere (FR-024)."""
    parsed = parse(url)
    if parsed is None:
        return []
    official = db.official_for_domain(parsed.registrable)
    out: list[Finding] = []
    if claims.orgs and (official is None or official.org not in claims.orgs):
        names = ", ".join(sorted(claims.orgs))
        out.append(Finding("claimed_org_domain_mismatch", "high",
                           f"message mentions {names} but the link goes to {parsed.registrable}"))
    elif claims.bank and parsed.suffix != "bank.in" and (
        official is None or official.org_type != "bank"
    ):
        out.append(Finding("bank_claim_non_bank_domain", "high",
                           f"message refers to a bank, but {parsed.registrable} is not a .bank.in "
                           "bank domain"))
    elif claims.government and parsed.suffix not in ("gov.in", "nic.in") and (
        official is None or official.org_type not in ("government", "regulator")
    ):
        out.append(Finding("gov_claim_non_gov_domain", "high",
                           f"message refers to a government body, but {parsed.registrable} is "
                           "not a .gov.in domain"))
    return out


def _designated_finding(entity: RawEntity) -> Finding:
    """TCCCPR Regulation 34A: designated series are never tagged or blocked (FR-081)."""
    # Series purposes: TCCCPR Third Amendment 2026, Explanatory Memorandum on reg. 34A
    # (docs/IndianOfficialDocs/Regulation_18092026.pdf, p.50).
    number = entity.value.strip()
    if entity.normalized.startswith("140"):
        detail = (f"{number} is from TRAI's 140 series, used by registered senders for "
                  "promotional calls. These calls are allowed unless you register a DND "
                  "preference by calling or sending an SMS to 1909; the number itself is not "
                  "labelled here")
    elif entity.normalized.startswith("1601"):
        detail = (f"{number} is from TRAI's 1601 series, being rolled out for service and "
                  "transaction calls, first from utilities, logistics and courier companies. "
                  "This suggests a genuine sender but is not proof; still verify the request")
    else:
        detail = (f"{number} is from TRAI's 1600 series, reserved for service and transaction "
                  "calls of RBI/SEBI/IRDAI/PFRDA-regulated entities and government. This "
                  "suggests a genuine sender but is not proof; still verify the request")
    return Finding("designated_series", "info", detail)


_HEADER_TYPES: Final = {
    "P": "promotional", "S": "service", "T": "transactional", "G": "government",
}


def _header_finding(entity: RawEntity) -> Finding:
    """Explain a DLT sender header's type suffix; never scored or labelled (FR-086).

    Government messages (-G) are covered by Regulation 34A, and headers can be misused
    (TCCCPR Third Amendment 2026), so the finding is informational and the content is still
    assessed on its own signals.
    """
    kind = _HEADER_TYPES[entity.value[-1]]
    detail = (f"{entity.value} is a TRAI-registered SMS header format; the -{entity.value[-1]} "
              f"suffix means a {kind} message. Registered headers can still be misused, so "
              "judge the request itself")
    if kind == "promotional":
        detail += "; promotional SMS can be blocked by calling or sending an SMS to 1909"
    return Finding("sender_header", "info", detail)


def _sender_format_findings(entity: RawEntity, claims: Claims) -> list[Finding]:
    """International numbers, and bank or government claims from non-designated numbers.

    Country is never scored (no nationality profiling, docs/08 section 5.1); only the mismatch
    between an international number and a claim to be an Indian authority is.
    """
    out: list[Finding] = []
    claims_authority = claims.bank or claims.government or bool(claims.orgs)
    if entity.international:
        out.append(Finding("international_number", "low",
                           f"{entity.masked()} is an international number ({entity.country_code})"))
        if claims_authority:
            out.append(Finding("authority_claim_international_number", "high",
                               "message claims to be from an Indian bank or government body but "
                               "uses an international number; DoT advises caution with such calls"))
    elif claims_authority:
        out.append(Finding("authority_claim_ordinary_mobile", "medium",
                           f"message claims to be from a bank or government body but uses an "
                           f"ordinary mobile number ({entity.masked()}); their service calls are "
                           "meant to come from the 1600 series"))
    return out


def run_intel(entities: list[RawEntity], text: str, db: IntelDB) -> IntelResult:
    claims = detect_claims(text, db)
    findings: list[IntelFinding] = []

    def add(entity: RawEntity, items: list[Finding]) -> None:
        for item in items:
            findings.append(
                IntelFinding(
                    entity_ref=entity.ref,
                    check=item.check,
                    severity=item.severity,
                    detail=item.detail,
                    evidence_id=f"I{len(findings) + 1}",
                )
            )

    for entity in entities:
        if entity.kind == "url":
            add(entity, analyze(entity.value, db) + _claim_mismatch(entity.value, claims, db))
        elif entity.kind == "phone" and entity.designated:
            # FR-081 / ADR-009: never blocklisted or labelled as scam or spam.
            add(entity, [_designated_finding(entity)])
        elif entity.kind == "sender_header":
            add(entity, [_header_finding(entity)])
        elif entity.kind in ("phone", "upi"):
            masked = entity.masked()
            known_good = db.allowlist_org(entity.kind, entity.normalized) is not None
            if entity.kind == "phone" and not known_good:
                add(entity, _sender_format_findings(entity, claims))
            if (category := db.blocklist_category(entity.kind, entity.normalized)) is not None:
                add(entity, [Finding("blocklist", "high",
                                     f"{entity.kind} {masked} is on the ScamSaathi demo blocklist "
                                     f"({category})")])
            elif (org := db.allowlist_org(entity.kind, entity.normalized)) is not None:
                add(entity, [Finding("allowlist", "info", f"{entity.kind} {masked} is a known "
                                     f"number of {org}")])
    return IntelResult(findings=findings)
