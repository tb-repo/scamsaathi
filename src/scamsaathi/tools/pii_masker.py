"""PII masking (task 1.4, FR-060, ADR-007).

Replaces personal identifiers with stable placeholders such as ``<PHONE_1>`` before any
text leaves the process or reaches a log. The original values stay in an in-memory map
so local tools (for example blocklist lookups) can still use them.

Phone numbers:
- Indian mobiles (+91 / 0091 / 0 prefixes) and international numbers (+CC or 00CC, 8 to 15
  digits, spaces, hyphens and brackets allowed) are masked as ``<PHONE_n>``. The same number
  written in different formats shares one placeholder.
- TRAI-designated number series (140xxxxxxx telemarketing, 1600xxxxxx / 1601xxxxxx service
  and transaction calls of regulated entities and government; docs/16 section 4) are
  organisation numbers, not personal data. They are left visible and never treated as PII.

Limitations (docs/08 L-1): regex masking cannot detect names or addresses.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

# Separator allowed inside digit groups: a single space or hyphen (never a newline).
_SEP = r"[ -]?"


def _digit_count_between(low: int, high: int) -> Callable[[str], bool]:
    def check(value: str) -> bool:
        digits = sum(ch.isdigit() for ch in value)
        return low <= digits <= high

    return check


# TRAI-designated series (10 digits): 140 + 7 digits, 1600/1601 + 6 digits.
DESIGNATED_SERIES: Final = re.compile(
    r"(?<![\d+])(?<!\d[ -])(?:\+91[ -]?)?(?:140(?:[ -]?\d){7}|160[01](?:[ -]?\d){6})(?![ -]?\d)"
)

# Order matters: earlier patterns claim spans first, later patterns skip overlaps.
# Each tuple is (placeholder kind, compiled pattern, optional validator).
_PATTERNS: Final[tuple[tuple[str, re.Pattern[str], Callable[[str], bool] | None], ...]] = (
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"),
        None,
    ),
    # UPI VPA: handle has no dot (e.g. name@okaxis). Emails were claimed above, so any
    # "name@domain.tld" never reaches this pattern.
    ("UPI", re.compile(r"\b[A-Za-z0-9][A-Za-z0-9._-]{1,255}@[A-Za-z][A-Za-z0-9]{1,63}\b"), None),
    # Indian mobile: optional +91 / 0091 / 0 prefix, then 10 digits starting 6-9.
    (
        "PHONE",
        re.compile(
            r"(?<!\d)(?<!\d[ -])(?:\+91" + _SEP + r"|0091" + _SEP + r"|0)?"
            r"[6-9]\d{4}" + _SEP + r"\d{5}(?![ -]?\d)"
        ),
        None,
    ),
    # International: + or 00, a country code other than 91, then digit groups that may be
    # separated by a space or hyphen and wrapped in brackets. 8 to 15 digits in total (E.164).
    (
        "PHONE",
        re.compile(
            r"(?<![\w+])(?:\+|00)(?!91)[1-9]\d{0,2}(?:[ -]?\(?\d{1,4}\)?){1,5}(?!\d)"
        ),
        _digit_count_between(8, 15),
    ),
    # Number embedded in a WhatsApp click-to-chat link: wa.me/<country code + number>.
    ("PHONE", re.compile(r"(?<=wa\.me/)\d{8,15}(?!\d)", re.IGNORECASE), None),
    # Contextual OTP / PIN / verification code: 4 to 8 digits preceded or followed by OTP context keywords.
    (
        "OTP",
        re.compile(
            r"(?i)\b(?:otp|one[- ]time[- ]password|verification[- ]code|security[- ]code|passcode|secret[- ]code|pin)\b(?:\s+(?:is|code|number))?[\s:= -]{1,5}(\d{4,8})\b"
            r"|\b(\d{4,8})\b(?:\s+(?:is\s+(?:your\s+)?|as\s+(?:your\s+)?)(?:otp|verification[- ]code|pin|passcode|code)\b)",
        ),
        None,
    ),
    # Aadhaar: 12 digits, first digit 2-9, optional 4-4-4 grouping.
    (
        "ID",
        re.compile(
            r"(?<!\d)(?<!\d[ -])[2-9]\d{3}" + _SEP + r"\d{4}" + _SEP + r"\d{4}(?![ -]?\d)"
        ),
        None,
    ),
    # PAN: AAAAA9999A (uppercase, as issued).
    ("ID", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), None),
    # IFSC: AAAA0XXXXXX.
    ("ID", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), None),
    # Account / card numbers: 9 to 19 digits with optional single separators.
    ("ACCT", re.compile(r"(?<!\d)(?<!\d[ -])\d(?:[ -]?\d){8,18}(?![ -]?\d)"), None),
)

# Query strings can carry tokens or identifiers; they are removed, not stored.
# Links with a scheme or "www.", and bare "domain.tld/path" links (e.g. wa.me/..., bit.ly/...).
_URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+|\b[\w-]+(?:\.[\w-]+)+/[^\s<>\"']*", re.IGNORECASE
)
QUERY_PLACEHOLDER: Final = "?<QUERY>"

_PLACEHOLDER = re.compile(r"<(?:EMAIL|UPI|PHONE|ID|ACCT|OTP)_\d+>")


@dataclass(frozen=True)
class MaskedEntity:
    """A masked span. ``span`` refers to positions in the original text."""

    kind: str
    placeholder: str
    span: tuple[int, int]


@dataclass(frozen=True)
class MaskResult:
    masked_text: str
    entities: tuple[MaskedEntity, ...]
    # Original values, keyed by placeholder. Excluded from repr so it is never logged by accident.
    mapping: dict[str, str] = field(repr=False)

    def original(self, placeholder: str) -> str | None:
        return self.mapping.get(placeholder)


def _query_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in _URL.finditer(text):
        query_at = match.group(0).find("?")
        if query_at != -1:
            start = match.start() + query_at
            fragment_at = match.group(0).find("#", query_at)
            end = match.start() + fragment_at if fragment_at != -1 else match.end()
            if end - start > 1:
                spans.append((start, end))
    return spans


def _overlaps(span: tuple[int, int], claimed: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in claimed)


@dataclass(frozen=True)
class PIIMatch:
    """A raw PII hit. Holds the original value: keep in memory only, never log or persist."""

    kind: str  # EMAIL, UPI, PHONE, ID, ACCT
    span: tuple[int, int]
    value: str = field(repr=False)


def find_designated(text: str) -> list[tuple[tuple[int, int], str]]:
    """Spans and values of TRAI-designated series numbers (not PII; safe to show)."""
    return [((m.start(), m.end()), m.group(0)) for m in DESIGNATED_SERIES.finditer(text)]


def find_pii(text: str, claimed: list[tuple[int, int]] | None = None) -> list[PIIMatch]:
    """Find PII in priority order; later patterns skip spans already claimed.

    Designated-series numbers are claimed first and never returned. Single source of truth
    for PII patterns, shared by the masker, the entity extractor, and the gateway check.
    """
    taken = list(claimed or []) + [span for span, _ in find_designated(text)]
    hits: list[PIIMatch] = []
    for kind, pattern, validator in _PATTERNS:
        for match in pattern.finditer(text):
            if match.lastindex is not None and match.lastindex >= 1:
                val = match.group(match.lastindex)
                span = (match.start(match.lastindex), match.end(match.lastindex))
            else:
                val = match.group(0)
                span = (match.start(), match.end())
            if _overlaps(span, taken) or (validator is not None and not validator(val)):
                continue
            taken.append(span)
            hits.append(PIIMatch(kind=kind, span=span, value=val))
    hits.sort(key=lambda hit: hit.span[0])
    return hits


def normalize_phone(value: str) -> str:
    """E.164 form: +91XXXXXXXXXX for Indian numbers, +<CC><number> otherwise."""
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    # An explicit country code, or more digits than an Indian number (e.g. wa.me/<cc><n>).
    if raw.startswith(("+", "00")) or len(digits) > 11:
        return f"+{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}"
    if len(digits) == 10:
        return f"+91{digits}"
    return digits


def is_international(normalized_phone: str) -> bool:
    return normalized_phone.startswith("+") and not normalized_phone.startswith("+91")


def canonical(kind: str, value: str) -> str:
    """Key used to decide whether two raw values are the same identifier."""
    if kind == "PHONE":
        return normalize_phone(value)
    return re.sub(r"[ -]", "", value).lower()


def mask(text: str, existing_mapping: dict[str, str] | None = None) -> MaskResult:
    """Mask PII in ``text``. Identical values get the same placeholder.

    If ``existing_mapping`` is provided, existing placeholders and their numbers are
    preserved and reused for identical values, with new identifiers continuing the sequence.
    """
    query_spans = _query_spans(text)
    found: list[tuple[int, int, str, str | None]] = [(s, e, "QUERY", None) for s, e in query_spans]
    found += [(h.span[0], h.span[1], h.kind, h.value) for h in find_pii(text, query_spans)]
    found.sort(key=lambda item: item[0])

    counters: dict[str, int] = {}
    by_value: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = dict(existing_mapping or {})
    if existing_mapping:
        for ph, orig in existing_mapping.items():
            m = re.match(r"^<([A-Z]+)_(\d+)>$", ph)
            if m:
                k, num = m.group(1), int(m.group(2))
                counters[k] = max(counters.get(k, 0), num)
                by_value[(k, canonical(k, orig))] = ph

    entities: list[MaskedEntity] = []
    pieces: list[str] = []
    cursor = 0

    for start, end, kind, original in found:
        pieces.append(text[cursor:start])
        if original is None:
            pieces.append(QUERY_PLACEHOLDER)
        else:
            key = (kind, canonical(kind, original))
            placeholder = by_value.get(key)
            if placeholder is None:
                counters[kind] = counters.get(kind, 0) + 1
                placeholder = f"<{kind}_{counters[kind]}>"
                by_value[key] = placeholder
                mapping[placeholder] = original
            pieces.append(placeholder)
            entities.append(MaskedEntity(kind=kind, placeholder=placeholder, span=(start, end)))
        cursor = end
    pieces.append(text[cursor:])

    return MaskResult(masked_text="".join(pieces), entities=tuple(entities), mapping=mapping)


def contains_pii(text: str) -> bool:
    """True if ``text`` still contains PII (placeholders and designated series are ignored).

    Used by the LLM gateway as a defence-in-depth check before any external call.
    """
    return bool(find_pii(_PLACEHOLDER.sub(" ", text)))


def mask_value(value: str) -> str:
    """Mask a single value on its own (for example a URL before it enters graph state)."""
    return mask(value).masked_text
