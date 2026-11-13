"""Lexical URL risk analysis (task 2.5, FR-021, docs/06 section 3.4).

Never fetches the URL. Each check returns a ``Finding``; the intel aggregator attaches
entity references and evidence IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from scamsaathi.schemas import Severity
from scamsaathi.tools.domains import (
    RESTRICTED_SUFFIXES,
    ParsedURL,
    brand_label,
    deconfuse,
    levenshtein,
    parse,
)
from scamsaathi.tools.intel_db import IntelDB

_LOGIN_WORDS: Final = re.compile(
    r"login|signin|verify|kyc|update|secure|account|bank|wallet|otp|reward|refund", re.IGNORECASE
)
MAX_SUBDOMAINS: Final = 3


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    detail: str


def _brands(db: IntelDB) -> dict[str, str]:
    """Brand label -> organisation, from official registrable domains and brand tokens."""
    brands: dict[str, str] = {}
    for official in db.official:
        parsed = parse(official.domain)
        if parsed is not None:
            brands[brand_label(parsed.registrable, parsed.suffix)] = official.org
        for token in official.brand_tokens:
            compact = token.replace(" ", "")
            if len(compact) >= 3:
                brands.setdefault(compact, official.org)
    return brands


def _host_tokens(parsed: ParsedURL) -> list[str]:
    return [t for t in re.split(r"[.-]", parsed.host) if t]


def _brand_in(tokens: list[str], brand: str) -> bool:
    for token in tokens:
        clean = deconfuse(token)
        if clean == brand:
            return True
        # Long brands also count when glued to other words, e.g. "hdfcnetbanking".
        if len(brand) >= 5 and (clean.startswith(brand) or clean.endswith(brand)):
            return True
    return False


def analyze(url: str, db: IntelDB) -> list[Finding]:
    parsed = parse(url)
    if parsed is None:
        return [Finding("unparseable_url", "medium", "link could not be parsed")]

    findings: list[Finding] = []
    host = parsed.host
    official = db.official_for_domain(parsed.registrable)

    if official is not None:
        state = "legacy domain" if official.status == "legacy" else "official domain"
        findings.append(Finding("official_domain", "info", f"{host} is the {state} of {official.org}"))
    elif parsed.suffix in RESTRICTED_SUFFIXES:
        kind = RESTRICTED_SUFFIXES[parsed.suffix]
        findings.append(
            Finding("restricted_suffix", "info", f"{host} uses the restricted .{parsed.suffix} "
                    f"domain, which is only issued to {kind} entities")
        )

    if parsed.registrable in db.shorteners or host in db.shorteners:
        findings.append(Finding("shortener", "medium", f"{host} is a URL shortener that hides "
                                "the real destination"))
    if parsed.is_ip:
        findings.append(Finding("ip_host", "high", "link points to a raw IP address"))
    if host.startswith("xn--") or ".xn--" in host or not host.isascii():
        findings.append(Finding("punycode", "high", "domain uses look-alike (punycode or "
                                "non-Latin) characters"))
    if parsed.has_userinfo:
        findings.append(Finding("userinfo_trick", "high", "link uses '@' to hide the real "
                                f"destination {host}"))
    if len(parsed.subdomains) > MAX_SUBDOMAINS:
        findings.append(Finding("excessive_subdomains", "medium", f"{host} has an unusually "
                                "long chain of subdomains"))
    if parsed.suffix in db.suspicious_tlds:
        findings.append(Finding("suspicious_tld", "low", f".{parsed.suffix} domains are often "
                                "used in phishing"))
    if parsed.scheme == "http" and _LOGIN_WORDS.search(url):
        findings.append(Finding("no_tls_sensitive", "medium", "unencrypted (http) link asking "
                                "for sensitive action"))

    if official is None and not parsed.is_ip:
        findings.extend(_impersonation_checks(parsed, db))

    blocked = db.blocklist_category("domain", parsed.registrable) or (
        db.blocklist_category("domain", host)
    )
    if blocked is not None:
        findings.append(Finding("blocklist", "high", f"{parsed.registrable} is on the ScamSaathi "
                                "demo blocklist"))
    return findings


def _impersonation_checks(parsed: ParsedURL, db: IntelDB) -> list[Finding]:
    findings: list[Finding] = []
    label = deconfuse(brand_label(parsed.registrable, parsed.suffix))
    tokens = _host_tokens(parsed)

    for brand, org in _brands(db).items():
        if _brand_in(tokens, brand):
            findings.append(Finding("brand_impersonation_domain", "high",
                                    f"{parsed.host} uses the name of {org} but is not its "
                                    "official domain"))
            return findings
        limit = 1 if len(brand) < 8 else 2
        if len(brand) >= 5 and 0 < levenshtein(label, brand, limit) <= limit:
            findings.append(Finding("lookalike_domain", "high",
                                    f"{parsed.registrable} looks like {org}'s domain but is "
                                    "spelled differently"))
            return findings
        if len(brand) >= 4 and brand in parsed.path.lower():
            findings.append(Finding("brand_in_path", "medium",
                                    f"link path mentions {org} on an unrelated domain"))
            return findings
    return findings
