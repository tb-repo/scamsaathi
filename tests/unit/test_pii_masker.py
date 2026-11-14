"""UT-PII-01..10 (FR-060). All values are synthetic."""

from __future__ import annotations

import pytest

from scamsaathi.tools.pii_masker import QUERY_PLACEHOLDER, contains_pii, mask


@pytest.mark.parametrize(
    "number",
    ["9876543210", "+91 9876543210", "+91-98765-43210", "09876543210", "98765 43210", "+919876543210"],
)
def test_ut_pii_01_indian_mobile_forms(number: str) -> None:
    result = mask(f"Call me on {number} now")
    assert result.masked_text == "Call me on <PHONE_1> now"
    assert result.original("<PHONE_1>") == number


def test_ut_pii_02_aadhaar_spaced_and_plain() -> None:
    result = mask("Aadhaar 2345 6789 0123 and 345678901234")
    assert result.masked_text == "Aadhaar <ID_1> and <ID_2>"


def test_ut_pii_03_pan_and_ifsc() -> None:
    result = mask("PAN ABCDE1234F, IFSC SBIN0001234")
    assert result.masked_text == "PAN <ID_1>, IFSC <ID_2>"


def test_ut_pii_04_upi_ids_including_sentence_end() -> None:
    result = mask("Pay to rahul.k@okaxis or shop99@ybl.")
    assert result.masked_text == "Pay to <UPI_1> or <UPI_2>."


def test_ut_pii_05_email_is_not_mistaken_for_upi() -> None:
    result = mask("Mail support.desk@example.co.in today")
    assert result.masked_text == "Mail <EMAIL_1> today"
    assert [e.kind for e in result.entities] == ["EMAIL"]


def test_ut_pii_06_amounts_dates_and_short_numbers_are_kept() -> None:
    text = "Pay Rs. 4,999 or ₹1,50,000 by 11/11/2026 at 10:30, valid 10 min, item #4829, pincode 560001"
    assert mask(text).masked_text == text


def test_ut_pii_contextual_otp_masking() -> None:
    res1 = mask("Your SBI OTP is 482910 for txn.")
    assert res1.masked_text == "Your SBI OTP is <OTP_1> for txn."
    assert res1.original("<OTP_1>") == "482910"

    res2 = mask("Use verification code: 918234 to log in.")
    assert res2.masked_text == "Use verification code: <OTP_1> to log in."
    assert res2.original("<OTP_1>") == "918234"

    res3 = mask("Your secret PIN is 1234. Do not share.")
    assert res3.masked_text == "Your secret PIN is <OTP_1>. Do not share."

    res4 = mask("Enter 654321 as your OTP.")
    assert res4.masked_text == "Enter <OTP_1> as your OTP."


def test_ut_pii_07_card_and_account_numbers() -> None:
    result = mask("Card 4111 1111 1111 1111 and account 123456789012345")
    assert result.masked_text == "Card <ACCT_1> and account <ACCT_2>"


def test_ut_pii_08_repeated_values_share_a_placeholder() -> None:
    result = mask("9876543210 called. Block 98765-43210. Also 9123456780.")
    assert result.masked_text == "<PHONE_1> called. Block <PHONE_1>. Also <PHONE_2>."
    assert len(result.mapping) == 2


def test_ut_pii_09_url_query_removed_and_digits_in_path_masked() -> None:
    result = mask("Open https://kyc-update.example/verify?token=abc123&id=77 or wa.me/919876543210")
    assert "token" not in result.masked_text
    assert f"https://kyc-update.example/verify{QUERY_PLACEHOLDER}" in result.masked_text
    assert "9876543210" not in result.masked_text


def test_ut_pii_09b_query_removed_from_bare_links() -> None:
    masked = mask("Tap bit.ly/abc?uid=u123 or wa.me/919876543210?text=hi").masked_text
    assert "uid=" not in masked and "text=hi" not in masked
    assert masked.count(QUERY_PLACEHOLDER) == 2


def test_ut_pii_10_edge_cases() -> None:
    assert mask("").masked_text == ""
    hinglish = "Aapka khata band ho jayega, turant 9876543210 pe call karein 🙏"
    assert mask(hinglish).masked_text == "Aapka khata band ho jayega, turant <PHONE_1> pe call karein 🙏"
    assert "mapping" not in repr(mask("9876543210"))


def test_contains_pii_ignores_placeholders() -> None:
    assert contains_pii("Call 9876543210")
    assert not contains_pii(mask("Call 9876543210, UPI a.b@ybl, PAN ABCDE1234F").masked_text)


def test_ut_pii_11_session_existing_mapping() -> None:
    first = mask("Call me at 9876543210")
    assert first.masked_text == "Call me at <PHONE_1>"

    # Answer mentions the same phone and adds a new one
    second = mask("I called 9876543210 and also 9123456780", existing_mapping=first.mapping)
    assert second.masked_text == "I called <PHONE_1> and also <PHONE_2>"
    assert second.mapping["<PHONE_1>"] == "9876543210"
    assert second.mapping["<PHONE_2>"] == "9123456780"

