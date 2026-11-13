"""Deterministic entity extraction (task 2.1, FR-010).

Runs on the original text inside the process. Returns ``RawEntity`` objects that hold
original values for local lookups (blocklists, URL analysis). Raw entities must never be
logged, put into graph state, or sent to an LLM (ADR-007, doc 05 conventions); use
``RawEntity.to_state()`` to get the masked ``Entity`` for state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Final

from scamsaathi.schemas import Entity, EntityFlag, EntityKind
from scamsaathi.tools.pii_masker import (
    MaskResult,
    canonical,
    find_designated,
    find_pii,
    is_international,
    mask,
    mask_value,
    normalize_phone,
)

# Bare domains (no scheme) are only accepted with TLDs seen in everyday and scam traffic;
# this avoids treating "Mr.Sharma" or "v1.2" as links.
_BARE_TLDS: Final = (
    "com|in|net|org|co|io|info|biz|me|ly|app|online|site|xyz|top|shop|club|live|vip|icu|"
    "link|click|buzz|store|tech|cc|tk|ml|ga|cf|gq|sbs|cfd|cyou|rest|bond|today|support|"
    "help|services|page|dev|ai|us|uk|example|test|invalid"
)
_URL_RE: Final = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+"
    r"|(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:" + _BARE_TLDS + r")\b"
    r"(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)
_TRAILING_PUNCT: Final = ".,;:!?)]}'\""

# TRAI DLT SMS sender header with its type suffix, e.g. "AX-HDFCBK-S". The suffix shows the
# message type: -P promotional, -S service, -T transactional, -G government (TCCCPR 2018 as
# amended on 12 Feb 2025, Schedule-I). Upper case only, so ordinary words do not match.
_HEADER_RE: Final = re.compile(r"(?<![\w-])[A-Z]{2}-[A-Z0-9]{3,11}-[PSTG](?![\w-])")

_AMOUNT_RE: Final = re.compile(
    r"(?:(?:₹|\brs\.?|\binr)\s?(?P<a>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<au>lakh|lac|crore|cr|k)\b)?)"
    r"|(?:\b(?P<b>\d[\d,]*(?:\.\d+)?)\s?(?P<bu>lakh|lac|crore|cr|k)?\s?(?:rupees?|rs\b|inr\b))",
    re.IGNORECASE,
)
_MULTIPLIER: Final = {"lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "cr": 10_000_000, "k": 1_000}

_PII_KIND: Final[dict[str, EntityKind]] = {
    "EMAIL": "email",
    "UPI": "upi",
    "PHONE": "phone",
    "ID": "id_number",
    "ACCT": "account_like",
}


@dataclass(frozen=True)
class RawEntity:
    """An extracted entity with its original value (in memory only).

    ``masked_form`` uses the same placeholders as the message-level masked text, so a
    finding about ``<PHONE_2>`` refers to the same ``<PHONE_2>`` the LLM sees.
    """

    ref: str  # "E1", "E2", ... stable within one request
    kind: EntityKind
    span: tuple[int, int]
    masked_form: str
    value: str = field(repr=False)
    normalized: str = field(repr=False)
    flags: tuple[EntityFlag, ...] = ()

    @property
    def international(self) -> bool:
        return "international" in self.flags

    @property
    def designated(self) -> bool:
        return "designated_series" in self.flags

    @property
    def country_code(self) -> str | None:
        """Country code of an international phone (not PII; e.g. "+44")."""
        if not self.international:
            return None
        for length in (1, 2, 3):
            code = self.normalized[1 : 1 + length]
            if code in _KNOWN_CC or length == 3:
                return f"+{code}"
        return None

    def masked(self) -> str:
        return self.masked_form

    def to_state(self) -> Entity:
        return Entity(
            kind=self.kind, value_ref=self.ref, masked=self.masked_form, span=self.span,
            flags=list(self.flags),
        )


# Common one- and two-digit calling codes, enough to display the country prefix only.
_KNOWN_CC: Final = frozenset(
    "1 7 20 27 30 31 32 33 34 36 39 40 41 43 44 45 46 47 48 49 51 52 53 54 55 56 57 58 60 61 "
    "62 63 64 65 66 81 82 84 86 90 92 93 94 95 98".split()
)


def _clean_url(raw: str) -> str:
    return raw.rstrip(_TRAILING_PUNCT)


def _parse_amount(number: str, unit: str | None) -> str | None:
    try:
        amount = Decimal(number.replace(",", ""))
    except InvalidOperation:
        return None
    if unit:
        amount *= _MULTIPLIER[unit.lower()]
    return str(amount.quantize(Decimal(1))) if amount == amount.to_integral() else str(amount)


def _kind_of(placeholder: str) -> str:
    return placeholder[1:].split("_", 1)[0]


def _mask_url(url: str, request_mask: MaskResult) -> str:
    """Mask a URL with the request-level placeholders (query removed, digits masked)."""
    local = mask(url)
    by_key = {
        (_kind_of(ph), canonical(_kind_of(ph), original)): ph
        for ph, original in request_mask.mapping.items()
    }
    out = local.masked_text
    # Longest placeholders first so "<PHONE_1>" never clips "<PHONE_10>".
    for ph in sorted(local.mapping, key=len, reverse=True):
        kind = _kind_of(ph)
        out = out.replace(ph, by_key.get((kind, canonical(kind, local.mapping[ph])), ph))
    return out


def extract(text: str, request_mask: MaskResult | None = None) -> list[RawEntity]:
    """Extract URLs, PII-type identifiers, sender headers, and amounts, ordered by position.

    ``request_mask`` should be ``mask(text)`` for the same text; computed if omitted.
    """
    request_mask = request_mask or mask(text)
    placeholder_at = {e.span: e.placeholder for e in request_mask.entities}
    Item = tuple[tuple[int, int], EntityKind, str, str, str, tuple[EntityFlag, ...]]
    found: list[Item] = []

    for match in _URL_RE.finditer(text):
        url = _clean_url(match.group(0))
        if not url:
            continue
        span = (match.start(), match.start() + len(url))
        found.append((span, "url", url, url.lower(), _mask_url(url, request_mask), ()))

    # PII inside URLs (for example wa.me/<number>) is still extracted as its own entity.
    for hit in find_pii(text):
        kind = _PII_KIND[hit.kind]
        flags: tuple[EntityFlag, ...] = ()
        if kind == "phone":
            normalized = normalize_phone(hit.value)
            if is_international(normalized):
                flags = ("international",)
        elif kind in ("upi", "email"):
            normalized = hit.value.lower()
        else:
            normalized = re.sub(r"[ -]", "", hit.value)
        masked_form = placeholder_at.get(hit.span) or mask_value(hit.value)
        found.append((hit.span, kind, hit.value, normalized, masked_form, flags))

    # TRAI-designated series numbers: organisation numbers, shown as written (FR-081).
    for span, value in find_designated(text):
        digits = re.sub(r"\D", "", value)[-10:]
        found.append((span, "phone", value, digits, value.strip(), ("designated_series",)))

    # Sender headers name an organisation, not a person, so they stay visible.
    for match in _HEADER_RE.finditer(text):
        header = match.group(0)
        found.append(((match.start(), match.end()), "sender_header", header, header, header, ()))

    for match in _AMOUNT_RE.finditer(text):
        number = match.group("a") or match.group("b")
        unit = match.group("au") or match.group("bu")
        parsed = _parse_amount(number, unit)
        if parsed is not None:
            # Amounts are not PII and help reasoning, so they stay visible (normalised).
            found.append(
                ((match.start(), match.end()), "amount", match.group(0), parsed, f"INR {parsed}", ())
            )

    found.sort(key=lambda item: (item[0][0], item[1]))
    return [
        RawEntity(
            ref=f"E{i}", kind=kind, span=span, masked_form=masked_form,
            value=value, normalized=normalized, flags=flags,
        )
        for i, (span, kind, value, normalized, masked_form, flags) in enumerate(found, start=1)
    ]
