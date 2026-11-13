"""UT-REP-01..05 (FR-022), UT-URL-01..10 (FR-021), claim checks (FR-024)."""

from __future__ import annotations

import pytest

from scamsaathi.tools.entities import extract
from scamsaathi.tools.intel import detect_claims, run_intel
from scamsaathi.tools.intel_db import IntelDB
from scamsaathi.tools.url_analyzer import analyze


def _checks(url: str, db: IntelDB) -> dict[str, str]:
    return {f.check: f.severity for f in analyze(url, db)}


def _intel_checks(text: str, db: IntelDB) -> list[str]:
    return [f.check for f in run_intel(extract(text), text, db).findings]


# --- Reputation ------------------------------------------------------------------


def test_ut_rep_01_blocklisted_phone(intel_db: IntelDB) -> None:
    result = run_intel(extract("Call 9000000001 now"), "Call 9000000001 now", intel_db)
    assert [(f.check, f.severity) for f in result.findings] == [("blocklist", "high")]
    assert "9000000001" not in result.findings[0].detail
    assert "<PHONE_1>" in result.findings[0].detail


def test_ut_rep_02_allowlisted_phone_is_info(intel_db: IntelDB) -> None:
    findings = run_intel(extract("Call 9000000099"), "Call 9000000099", intel_db).findings
    assert [(f.check, f.severity) for f in findings] == [("allowlist", "info")]


def test_ut_rep_03_normalisation_of_formats(intel_db: IntelDB) -> None:
    for text in ("+91 90000 00001", "+91-90000-00001", "09000000001"):
        assert _intel_checks(text, intel_db) == ["blocklist"], text


def test_ut_rep_04_unknown_values_produce_no_findings(intel_db: IntelDB) -> None:
    assert _intel_checks("Call 9123456780 or pay someone@okaxis", intel_db) == []


def test_ut_rep_05_upi_case_insensitive_and_evidence_ids(intel_db: IntelDB) -> None:
    text = "Pay Refund.Helpdesk@DEMO and lottery.claim@demo"
    findings = run_intel(extract(text), text, intel_db).findings
    assert [f.check for f in findings] == ["blocklist", "blocklist"]
    assert [f.evidence_id for f in findings] == ["I1", "I2"]


# --- URL analysis -----------------------------------------------------------------


def test_ut_url_01_lookalike_domain(intel_db: IntelDB) -> None:
    assert _checks("https://hdfcbnak.com/login", intel_db)["lookalike_domain"] == "high"


def test_ut_url_02_brand_in_subdomain(intel_db: IntelDB) -> None:
    checks = _checks("https://sbi.bank.in.secure-verify.xyz/kyc", intel_db)
    assert checks["brand_impersonation_domain"] == "high"
    assert checks["suspicious_tld"] == "low"
    assert "official_domain" not in checks


def test_ut_url_03_ip_host_without_tls(intel_db: IntelDB) -> None:
    checks = _checks("http://192.168.10.5/kyc-update", intel_db)
    assert checks["ip_host"] == "high" and checks["no_tls_sensitive"] == "medium"


def test_ut_url_04_punycode(intel_db: IntelDB) -> None:
    assert _checks("https://xn--sbi-k5a.com", intel_db)["punycode"] == "high"


def test_ut_url_05_userinfo_trick(intel_db: IntelDB) -> None:
    checks = _checks("https://sbi.bank.in@evil-site.example/login", intel_db)
    assert checks["userinfo_trick"] == "high"
    assert "official_domain" not in checks


def test_ut_url_06_official_bank_in_domain(intel_db: IntelDB) -> None:
    findings = analyze("https://sbi.bank.in/web/personal-banking", intel_db)
    assert [(f.check, f.severity) for f in findings] == [("official_domain", "info")]


def test_ut_url_07_legacy_domain_recognised(intel_db: IntelDB) -> None:
    finding = analyze("https://www.hdfcbank.com", intel_db)[0]
    assert finding.check == "official_domain" and "legacy" in finding.detail


def test_ut_url_08_shortener(intel_db: IntelDB) -> None:
    assert _checks("bit.ly/3xYz9", intel_db)["shortener"] == "medium"


def test_ut_url_09_blocklisted_domain(intel_db: IntelDB) -> None:
    checks = _checks("http://sbi-kyc-update.example/login", intel_db)
    assert checks["blocklist"] == "high"
    assert checks["brand_impersonation_domain"] == "high"
    assert checks["no_tls_sensitive"] == "medium"


@pytest.mark.parametrize("url", ["https://www.wikipedia.org", "https://docs.python.org/3/"])
def test_ut_url_10_benign_urls_have_no_findings(intel_db: IntelDB, url: str) -> None:
    assert analyze(url, intel_db) == []


# --- Claimed sender vs link (FR-024) ----------------------------------------------


def test_claim_detection(intel_db: IntelDB) -> None:
    claims = detect_claims("SBI alert: your YONO account is blocked", intel_db)
    assert claims.orgs == {"State Bank of India"} and claims.bank
    assert detect_claims("CBI officer calling", intel_db).government


def test_bank_claim_with_non_bank_domain(intel_db: IntelDB) -> None:
    checks = _intel_checks("Your bank KYC expired, update at https://kyc-help.example", intel_db)
    assert "bank_claim_non_bank_domain" in checks


def test_named_org_with_wrong_domain(intel_db: IntelDB) -> None:
    checks = _intel_checks("India Post: parcel held, pay at indiapost-redelivery.test", intel_db)
    assert "claimed_org_domain_mismatch" in checks and "blocklist" in checks


def test_named_org_with_its_own_domain_is_clean(intel_db: IntelDB) -> None:
    checks = _intel_checks("HDFC Bank statement: https://www.hdfc.bank.in/statements", intel_db)
    assert checks == ["official_domain"]
