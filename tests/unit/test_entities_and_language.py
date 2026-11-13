"""UT-ENT-01..08 (FR-010) and UT-LANG (FR-002). Synthetic values only."""

from __future__ import annotations

import pytest

from scamsaathi.schemas import Language
from scamsaathi.tools.entities import extract
from scamsaathi.tools.language import detect
from scamsaathi.tools.pii_masker import mask


def _kinds(text: str) -> list[tuple[str, str]]:
    return [(e.kind, e.normalized) for e in extract(text)]


def test_ut_ent_01_urls_with_and_without_scheme() -> None:
    text = "Visit https://sbi-kyc-update.example/login, www.hdfc.bank.in or bit.ly/3xYz9."
    urls = [n for k, n in _kinds(text) if k == "url"]
    assert urls == ["https://sbi-kyc-update.example/login", "www.hdfc.bank.in", "bit.ly/3xyz9"]


def test_ut_ent_02_names_and_versions_are_not_urls() -> None:
    assert [k for k, _ in _kinds("Mr.Sharma said v1.2 is fine, e.g. tomorrow")] == []


def test_ut_ent_03_phone_forms_normalised_to_e164() -> None:
    text = "Call +91 90000 00001 or 9000000002 or 0-9000000003"
    phones = [n for k, n in _kinds(text) if k == "phone"]
    assert phones[:2] == ["+919000000001", "+919000000002"]


def test_ut_ent_04_upi_and_email_lowercased() -> None:
    kinds = _kinds("Pay Refund.Helpdesk@DEMO or mail Help@Example.COM")
    assert ("upi", "refund.helpdesk@demo") in kinds
    assert ("email", "help@example.com") in kinds


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("Pay Rs. 4,999 now", "4999"),
        ("fee of ₹1,50,000", "150000"),
        ("send 5000 rupees", "5000"),
        ("prize of Rs 25 lakh", "2500000"),
        ("INR 2.5 crore", "25000000"),
    ],
)
def test_ut_ent_05_amounts(text: str, amount: str) -> None:
    assert ("amount", amount) in _kinds(text)


def test_ut_ent_06_phone_inside_whatsapp_link() -> None:
    kinds = [k for k, _ in _kinds("Chat on wa.me/919000000001 now")]
    assert "url" in kinds and ("id_number" in kinds or "phone" in kinds)


def test_ut_ent_07_masked_forms_match_message_placeholders() -> None:
    text = "Call 9000000001, then 9000000002, then visit wa.me/919000000002?ref=abc"
    request_mask = mask(text)
    entities = extract(text, request_mask)
    phones = [e for e in entities if e.kind == "phone"]
    # The number inside the wa.me link is the same as the second phone, so it shares <PHONE_2>.
    assert [p.masked() for p in phones] == ["<PHONE_1>", "<PHONE_2>", "<PHONE_2>"]
    url = next(e for e in entities if e.kind == "url")
    assert "ref=abc" not in url.masked() and "9000000002" not in url.masked()
    for entity in entities:
        state = entity.to_state()
        assert "9000000001" not in state.masked and state.value_ref.startswith("E")


def test_ut_ent_08_raw_values_hidden_from_repr_and_refs_sequential() -> None:
    entities = extract("UPI refund.helpdesk@demo, call 9000000001")
    assert "refund.helpdesk" not in repr(entities) and "9000000001" not in repr(entities)
    assert [e.ref for e in entities] == [f"E{i}" for i in range(1, len(entities) + 1)]


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Your account will be blocked today, update KYC now", Language.EN),
        ("Aapka khata band ho jayega, turant KYC update karein", Language.HINGLISH),
        ("Main CBI officer bol raha hoon, kisi ko mat batana", Language.HINGLISH),
        ("आपका खाता बंद हो जाएगा, तुरंत केवाईसी अपडेट करें", Language.HI),
        ("உங்கள் கணக்கு முடக்கப்படும்", Language.OTHER),
        ("12345 !!!", Language.OTHER),
    ],
)
def test_ut_lang_detection(text: str, language: Language) -> None:
    assert detect(text).language is language
