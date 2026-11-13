"""URL and domain helpers used by the URL analyzer (task 2.5).

No network access: URLs are parsed lexically and never fetched (docs/08 T-08).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

# Multi-label public suffixes relevant to India plus a few common ones. Enough for
# registrable-domain extraction in this prototype without a public-suffix dependency.
_MULTI_SUFFIXES: Final = frozenset(
    {
        "bank.in", "co.in", "gov.in", "nic.in", "org.in", "net.in", "ac.in", "edu.in",
        "res.in", "firm.in", "gen.in", "ind.in", "fin.in",
        "co.uk", "org.uk", "gov.uk", "com.au", "co.jp",
    }
)
# Domains only issuable to vetted entities: RBI-mandated bank domain (registrar IDRBT)
# and Government of India domains (registrar NIC).
RESTRICTED_SUFFIXES: Final = {"bank.in": "bank", "gov.in": "government", "nic.in": "government"}

_HOMOGLYPHS: Final = (("rn", "m"), ("vv", "w"), ("0", "o"), ("1", "l"), ("3", "e"),
                      ("5", "s"), ("@", "a"), ("$", "s"), ("!", "i"), ("|", "l"))


@dataclass(frozen=True)
class ParsedURL:
    scheme: str
    host: str
    registrable: str  # e.g. "sbi.bank.in", "secure-login.xyz"
    suffix: str  # e.g. "bank.in", "xyz"
    subdomains: tuple[str, ...]
    path: str
    has_userinfo: bool
    is_ip: bool


def parse(url: str) -> ParsedURL | None:
    candidate = url if "://" in url else f"http://{url}"
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").rstrip(".").lower()
    except ValueError:
        return None
    if not host:
        return None

    is_ip = _is_ip(host)
    labels = host.split(".")
    subs: tuple[str, ...]
    if is_ip or len(labels) < 2:
        suffix, registrable, subs = "", host, ()
    else:
        last_two = ".".join(labels[-2:])
        if last_two in _MULTI_SUFFIXES and len(labels) >= 3:
            suffix, registrable, subs = last_two, ".".join(labels[-3:]), tuple(labels[:-3])
        else:
            suffix, registrable, subs = labels[-1], last_two, tuple(labels[:-2])

    return ParsedURL(
        scheme=parts.scheme.lower() if "://" in url else "",
        host=host,
        registrable=registrable,
        suffix=suffix,
        subdomains=subs,
        path=parts.path or "",
        has_userinfo="@" in (parts.netloc or ""),
        is_ip=is_ip,
    )


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def brand_label(registrable: str, suffix: str) -> str:
    """The label before the suffix: "hdfc" for hdfc.bank.in, "hdfcbank" for hdfcbank.com."""
    if suffix and registrable.endswith("." + suffix):
        return registrable[: -(len(suffix) + 1)]
    return registrable.split(".")[0]


def deconfuse(label: str) -> str:
    """Map common look-alike characters to their letter forms (for lookalike checks)."""
    out = label.lower()
    for fake, real in _HOMOGLYPHS:
        out = out.replace(fake, real)
    return out.replace("-", "")


def levenshtein(a: str, b: str, limit: int = 3) -> int:
    """Edit distance with early exit once it exceeds ``limit``."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]
