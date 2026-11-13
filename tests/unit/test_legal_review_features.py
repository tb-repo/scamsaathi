"""Features added after the legal and regulatory review (docs/16; FR-080 to FR-085).

UT-REG-01..05 plus international-number handling, new signals, and the child-safety path.
All numbers and messages are synthetic.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scamsaathi.config import PROJECT_ROOT
from scamsaathi.kb.advice import build_advice
from scamsaathi.kb.store import load_kb
from scamsaathi.pipeline.baseline import assess
from scamsaathi.schemas import SignalName
from scamsaathi.tools import rule_signals
from scamsaathi.tools.entities import extract
from scamsaathi.tools.intel import run_intel
from scamsaathi.tools.intel_db import IntelDB
from scamsaathi.tools.pii_masker import contains_pii, mask, normalize_phone
from scamsaathi.tools.risk_scorer import Situation

# --- International numbers (masking gap found on 2026-11-12) -------------------------


@pytest.mark.parametrize(
    ("raw", "e164"),
    [
        ("+447700900123", "+447700900123"),
        ("+44 7700 900123", "+447700900123"),
        ("+92 300 1234567", "+923001234567"),
        ("+1 (202) 555-0143", "+12025550143"),
        ("+254 712 345 678", "+254712345678"),
        ("00971501234567", "+971501234567"),
    ],
)
def test_international_numbers_are_masked_as_phones(raw: str, e164: str) -> None:
    result = mask(f"Call {raw} now")
    assert result.masked_text == "Call <PHONE_1> now", result.masked_text
    assert not contains_pii(result.masked_text)
    assert normalize_phone(raw) == e164


def test_whatsapp_link_number_is_a_phone_and_shares_placeholder() -> None:
    result = mask("Call +44 7700 900123 or chat on wa.me/447700900123")
    assert result.masked_text == "Call <PHONE_1> or chat on wa.me/<PHONE_1>"


def test_small_plus_numbers_are_not_phones() -> None:
    assert mask("Score +1000 points, +5 bonus").masked_text == "Score +1000 points, +5 bonus"


def test_international_entities_flagged_with_country_code_only() -> None:
    entities = [e for e in extract("Call +92 300 1234567") if e.kind == "phone"]
    assert entities and entities[0].international
    assert entities[0].country_code == "+92"
    assert entities[0].to_state().flags == ["international"]
    assert "300" not in entities[0].masked()


# --- UT-REG-01/02: TRAI-designated series (FR-081) -----------------------------------


@pytest.mark.parametrize("number", ["1600123456", "1601 234 567", "1401234567", "+91 1600123456"])
def test_ut_reg_01_designated_series_visible_and_not_pii(number: str) -> None:
    text = f"Our service team will call from {number}"
    assert mask(text).masked_text == text
    assert not contains_pii(text)
    entity = next(e for e in extract(text) if e.kind == "phone")
    assert entity.designated and entity.masked() == number.strip()


def test_ut_reg_02_designated_series_never_labelled(intel_db: IntelDB) -> None:
    text = "HDFC Bank will call you from 1600123456 about your card"
    findings = run_intel(extract(text), text, intel_db).findings
    assert [(f.check, f.severity) for f in findings] == [("designated_series", "info")]
    assert "1600 series" in findings[0].detail
    assert assess(text, intel_db).risk.level == "LOW"


def test_ut_reg_02b_blocklist_rejects_designated_series(tmp_path: Path) -> None:
    data = tmp_path / "intel"
    shutil.copytree(PROJECT_ROOT / "data" / "intel", data)
    with (data / "blocklist.csv").open("a", encoding="utf-8") as handle:
        handle.write("phone,1600123456,SC-02,synthetic,2026-11-12\n")
    with pytest.raises(ValueError, match="designated-series"):
        IntelDB.build(data)


# --- UT-REG-03: sender-format signal (FR-082) ----------------------------------------


def test_ut_reg_03_authority_claim_from_international_number(intel_db: IntelDB) -> None:
    text = "CBI officer calling from +971501234567. You are under digital arrest."
    checks = {f.check: f.severity for f in run_intel(extract(text), text, intel_db).findings}
    assert checks["international_number"] == "low"
    assert checks["authority_claim_international_number"] == "high"


def test_ut_reg_03b_bank_claim_from_ordinary_mobile(intel_db: IntelDB) -> None:
    text = "SBI KYC team: call 9123456780 to avoid account block"
    checks = {f.check: f.severity for f in run_intel(extract(text), text, intel_db).findings}
    assert checks["authority_claim_ordinary_mobile"] == "medium"


def test_ut_reg_03c_family_abroad_stays_low(intel_db: IntelDB) -> None:
    text = "Hi Amma, this is Ravi, call me on +44 7700 900123 when free, love you"
    result = assess(text, intel_db)
    assert result.risk.level == "LOW"
    assert [f.check for f in result.intel.findings] == ["international_number"]


def test_ut_reg_03d_allowlisted_number_has_no_sender_finding(intel_db: IntelDB) -> None:
    text = "Bank helpline 9000000099"
    checks = [f.check for f in run_intel(extract(text), text, intel_db).findings]
    assert checks == ["allowlist"]


# --- New signals (SC-13 to SC-15) -----------------------------------------------------


def _names(text: str) -> set[SignalName]:
    return {s.name for s in rule_signals.detect(text, has_link=False)}


@pytest.mark.parametrize(
    ("text", "signal"),
    [
        ("Pay Rs 20,000 or I will send your video call recording to all your contacts",
         SignalName.SEXTORTION_THREAT),
        ("Paise bhejo warna tumhara video sab contacts ko bhej dunga", SignalName.SEXTORTION_THREAT),
        ("Let us use your bank account and UPI ID, you get commission monthly",
         SignalName.MONEY_MULE_REQUEST),
        ("Apna account kiraye pe do, har transaction pe commission", SignalName.MONEY_MULE_REQUEST),
        ("Win Rs 10,000 daily on colour prediction", SignalName.MONEY_GAME),
        ("Aviator game khelo, roz 5000 jeeto", SignalName.MONEY_GAME),
    ],
)
def test_new_signals_detected(text: str, signal: SignalName) -> None:
    assert signal in _names(text)


@pytest.mark.parametrize("text", ["Earn Rs 2000 per day", "Win Rs 10,000 daily", "earn ₹500"])
def test_reward_amounts_with_several_digits(text: str) -> None:
    """Regression: '\\d\\b' failed when more digits followed (found 2026-11-12)."""
    assert SignalName.REWARD_PROMISE in _names(text)


@pytest.mark.parametrize(
    "text",
    [
        "Please share the photos from the wedding with the family",
        "You can use your account to log in to the app",
        "Our cricket team won the match today",
    ],
)
def test_new_signals_ignore_everyday_text(text: str) -> None:
    assert not _names(text) & {
        SignalName.SEXTORTION_THREAT, SignalName.MONEY_MULE_REQUEST, SignalName.MONEY_GAME
    }


# --- Child-safety path (UT-REG-04) ----------------------------------------------------


def test_ut_reg_04_child_safety_detected_and_routed(intel_db: IntelDB) -> None:
    text = ("Someone is threatening my daughter, she is 14 years old, saying they will post her "
            "morphed photos unless we pay")
    result = assess(text, intel_db)
    assert result.situation.child_involved
    assert result.risk.level == "CRITICAL" and "child_safety" in result.risk.overrides

    bundle = build_advice(load_kb(), result.risk.level, ["SC-14"], result.situation)
    assert "police" in bundle.actions[0].text.lower()
    assert any("do not forward" in a.text.lower() for a in bundle.actions)
    assert [c.value for c in bundle.contacts] == ["112", "https://cybercrime.gov.in"]


def test_child_safety_needs_both_indicators() -> None:
    assert not rule_signals.detect_child_safety("My son lost his phone at school")
    assert not rule_signals.detect_child_safety("They threatened to share morphed photos of me")


# --- UT-REG-05: advice content from the Acts, facts only (FR-083) ---------------------


def test_ut_reg_05_urgent_advice_has_evidence_and_police_steps() -> None:
    kb = load_kb()
    bundle = build_advice(kb, "HIGH", ["SC-04"], Situation(money_sent=True))
    texts = " ".join(a.text for a in bundle.actions).lower()
    assert "any police station" in texts and "free copy" in texts
    assert "utr" in texts and "do not delete" in texts


def test_ut_reg_05b_user_facing_text_never_names_sections() -> None:
    import re

    kb = load_kb()
    section = re.compile(r"\b(?:section|sec\.|s\.\s?\d|u/s|bns|ipc|it act)\b", re.I)
    a = kb.advice
    texts = (a.urgent_recovery + a.child_safety + a.evidence + a.police_reporting
             + [t for items in a.by_level.values() for t in items]
             + [t for items in a.by_typology.values() for t in items]
             + [t for ty in kb.typologies.values() for t in ty.recommended_actions])
    offenders = [t for t in texts if section.search(t)]
    assert offenders == []


# --- Official websites review (docs/IndianOfficialWebSites, 2026-11-12) ----------------


def test_suspected_fraud_advice_mentions_chakshu_30_day_window() -> None:
    bundle = build_advice(load_kb(), "MEDIUM", ["SC-02"])
    assert any("within 30 days" in a.text for a in bundle.actions)
    assert "https://sancharsaathi.gov.in/sfc" in [c.value for c in bundle.contacts]


def test_digital_arrest_adds_report_international_call_page() -> None:
    values = [c.value for c in build_advice(load_kb(), "HIGH", ["SC-01"]).contacts]
    assert "https://sancharsaathi.gov.in/InternationalCall/ReportIntCall.jsp" in values


def test_money_mule_adds_know_your_connections() -> None:
    bundle = build_advice(load_kb(), "MEDIUM", ["SC-15"])
    names = [c.name for c in bundle.contacts]
    assert any("Know Mobile Connections" in n for n in names)
    assert any("registered in your name" in a.text for a in bundle.actions)


def test_telemarketing_number_routes_to_spam_reporting() -> None:
    bundle = build_advice(load_kb(), "LOW", [], telemarketing_number=True)
    assert [c.value for c in bundle.contacts] == ["1909", "https://sancharsaathi.gov.in/sfc"]
    assert any("DND registry" in a.text for a in bundle.actions)


# --- TRAI TCCCPR amendments (Regulation_12022025.pdf; PIB release 2311989, 2026-11-13) ----


def test_spam_advice_states_7_day_ucc_complaint_window_and_fields() -> None:
    texts = " ".join(a.text for a in build_advice(load_kb(), "LOW", [],
                                                  telemarketing_number=True).actions)
    assert "within 7 days" in texts and "1909" in texts
    assert "sender's number" in texts and "date" in texts


def test_spam_route_not_shown_when_money_was_lost() -> None:
    bundle = build_advice(load_kb(), "HIGH", [], Situation(money_sent=True),
                          telemarketing_number=True)
    assert "1909" not in [c.value for c in bundle.contacts]


@pytest.mark.parametrize(
    ("header", "kind"),
    [("AX-HDFCBK-S", "service"), ("VM-AMAZON-P", "promotional"),
     ("JD-UIDAI-G", "government"), ("BP-SBIOTP-T", "transactional")],
)
def test_sender_header_type_is_explained_not_scored(
    intel_db: IntelDB, header: str, kind: str
) -> None:
    text = f"{header}: Your request has been received. Thank you."
    entity = next(e for e in extract(text) if e.kind == "sender_header")
    assert entity.masked() == header and entity.to_state().masked == header
    findings = run_intel(extract(text), text, intel_db).findings
    assert [(f.check, f.severity) for f in findings] == [("sender_header", "info")]
    assert f"{kind} message" in findings[0].detail
    assert assess(text, intel_db).risk.level == "LOW"


def test_government_header_does_not_hide_scam_content(intel_db: IntelDB) -> None:
    """Regulation 34A: never tag the header, but header misuse is real (2026 amendment)."""
    text = ("JD-UIDAI-G: Your Aadhaar will be blocked today. Share the OTP and pay Rs 500 "
            "at http://aadhaar-update.xyz/verify")
    result = assess(text, intel_db)
    assert result.risk.level in ("HIGH", "CRITICAL")
    header = [f for f in result.intel.findings if f.check == "sender_header"]
    assert len(header) == 1 and header[0].severity == "info"


@pytest.mark.parametrize(
    "text",
    ["Meet at AB-12 block", "Ref no. XY-1234", "ax-hdfcbk-s lower case", "AX-HDFCBK-Q",
     "Model AX-HDFCBK-S2"],
)
def test_header_pattern_ignores_lookalikes(text: str) -> None:
    assert not [e for e in extract(text) if e.kind == "sender_header"]


# --- TCCCPR Third Amendment 2026, Gazette text (Regulation_18092026.pdf) ----------------


def test_1601_series_described_as_utilities_logistics_courier(intel_db: IntelDB) -> None:
    """Direction of 10 Aug 2026 (EM p.50): 1601xx is not the RBI/SEBI series."""
    text = "Your courier company will call you from 1601234567"
    finding = run_intel(extract(text), text, intel_db).findings[0]
    assert finding.check == "designated_series" and finding.severity == "info"
    assert "1601 series" in finding.detail and "courier" in finding.detail
    assert "RBI" not in finding.detail


def test_140_series_not_called_spam(intel_db: IntelDB) -> None:
    """EM p.50: 140xx calls cannot be termed spam unless the recipient has opted out."""
    text = "Special offer on home loans, call 1401234567"
    finding = run_intel(extract(text), text, intel_db).findings[0]
    assert finding.check == "designated_series"
    assert "spam" not in finding.detail.lower() and "DND" in finding.detail


def test_spam_advice_complaint_is_conditional_on_opt_out() -> None:
    texts = [a.text for a in build_advice(load_kb(), "LOW", [], telemarketing_number=True).actions]
    opt_out = next(t for t in texts if "allowed unless you opt out" in t)
    complaint = next(t for t in texts if "after you opt out" in t)
    assert texts.index(opt_out) < texts.index(complaint)
    assert "SMS header" in complaint  # reg. 25(2): sender's number or header is needed


def test_low_risk_without_telemarketing_has_no_contacts() -> None:
    assert build_advice(load_kb(), "LOW", ["SC-01"]).contacts == []


def test_every_legal_ref_points_to_an_act_in_the_repo() -> None:
    kb = load_kb()
    for typology in kb.typologies.values():
        for ref in typology.legal_refs:
            source = kb.sources[ref.split(" ", 1)[0]]
            assert source.path and (PROJECT_ROOT / source.path).exists(), ref
