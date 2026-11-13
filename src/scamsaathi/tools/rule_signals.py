"""Rule-based behavioural signal detection (task 2.7; fallback for A2, pre-screen input).

Runs on **masked** text, so evidence spans are safe to store and show. Patterns cover
English and common romanised Hindi (Hinglish). Rules are deliberately conservative and
get a fixed, moderate confidence; the LLM extractor (Phase 4) refines them.
"""

from __future__ import annotations

import re
from typing import Final

from scamsaathi.schemas import Signal, SignalName

RULE_CONFIDENCE: Final = 0.7
_SECRET: Final = r"(?:otp|o\.t\.p|one[- ]time password|pin|cvv|password|passcode|verification code|code)"
_ASK: Final = (
    r"(?:share|send|tell|give|provide|enter|forward|read out|confirm|batao|bataiye|bata do|"
    r"bhejo|bhej do|bhejiye|dijiye|de do|daalo|dalo)"
)
# Negations that turn "share OTP" into a legitimate safety notice.
_NEGATION: Final = re.compile(
    r"(?:do not|don't|dont|never|not to|mat|na|nahi|nahin|kabhi bhi)\W+(?:\w+\W+){0,6}$", re.I
)

_RULES: Final[dict[SignalName, re.Pattern[str]]] = {
    SignalName.URGENCY: re.compile(
        r"\b(?:urgent(?:ly)?|immediately|right now|asap|within \d+ ?(?:hours?|hrs?|minutes?|mins?)|"
        r"today itself|by tonight|tonight|last (?:chance|warning|reminder|day)|expires? (?:today|soon)|"
        r"turant|jaldi|abhi ke abhi|fauran|aaj hi)\b",
        re.I,
    ),
    SignalName.THREAT: re.compile(
        r"\b(?:block(?:ed)?|suspend(?:ed)?|deactivat(?:ed|ion)|disconnect(?:ed|ion)?|legal action|"
        r"arrest(?:ed)?|warrant|fir|penalty|seiz(?:e|ed)|cut off|terminat(?:e|ed)|freez(?:e|ed)|"
        r"band ho (?:jayega|jayegi|jaega)|kat (?:jayega|jayegi)|giraftar)\b",
        re.I,
    ),
    SignalName.SECRECY: re.compile(
        r"(?:do not|don't|dont) (?:tell|inform) (?:anyone|anybody|your family)|"
        r"keep (?:this|it) (?:confidential|secret)|stay on (?:the )?(?:video )?call|"
        r"(?:do not|don't) (?:disconnect|cut) the call|kisi ko (?:mat|na|nahi) bata",
        re.I,
    ),
    SignalName.AUTHORITY_IMPERSONATION: re.compile(
        r"\b(?:police|cbi|customs|ed officer|enforcement directorate|narcotics|ncb|court|judge|"
        r"rbi|trai|income tax|cyber (?:cell|crime)|crime branch|bank (?:officer|manager|executive)|"
        r"customer care|kyc|government|govt)\b",
        re.I,
    ),
    SignalName.PAYMENT_REQUEST: re.compile(
        r"\b(?:pay|transfer|send money|deposit|scan (?:the |this )?qr|collect request|"
        r"approve (?:the )?request|paise bhejo|paisa bhejo|bhugtan|jama kar(?:o|ein))\b",
        re.I,
    ),
    SignalName.APP_INSTALL_REQUEST: re.compile(
        r"\b(?:download|install)\b.{0,40}?\b(?:app|apk|anydesk|teamviewer|quick ?support|rustdesk)\b|"
        r"\b(?:anydesk|teamviewer|rustdesk)\b|\.apk\b",
        re.I,
    ),
    SignalName.REWARD_PROMISE: re.compile(
        r"\b(?:you (?:have )?won|winner|lottery|prize|lucky draw|jackpot|congratulations|"
        r"selected for|cashback of|free gift|earn (?:rs\.?|₹|inr)?\s?\d[\d,]*|"
        r"win (?:rs\.?|₹|inr)?\s?\d[\d,]*|"
        r"daily income|guaranteed (?:returns?|profit|winnings)|inaam|jeeto)\b",
        re.I,
    ),
    SignalName.ADVANCE_FEE: re.compile(
        r"\b(?:processing|registration|clearance|activation|release|delivery|verification|"
        r"customs|gst|tax) (?:fee|charges?|amount|duty)\b|"
        r"\bpay\b.{0,40}?\bto (?:claim|receive|release|unlock|get)\b",
        re.I,
    ),
    SignalName.EMOTIONAL_PRESSURE: re.compile(
        r"\b(?:emergency|accident|hospital|in trouble|help me|please help|i'?m stuck|"
        r"mera phone kho gaya|madad karo)\b",
        re.I,
    ),
    SignalName.UNKNOWN_SENDER_CLAIM: re.compile(
        r"\b(?:my new number|this is my new|changed my number|mera naya number|new number hai)\b",
        re.I,
    ),
    # Threat to share intimate, nude, or morphed images or recordings (SC-14).
    # Needs sensitive content words, or (Hinglish) a "pay or else ... I will send the video" frame;
    # ordinary "share the photos" must not match.
    SignalName.SEXTORTION_THREAT: re.compile(
        r"\b(?:leak|share|send|post|upload|viral|forward|publish)\b.{0,60}?\b(?:nude|naked|"
        r"obscene|intimate|private (?:photos?|videos?|pics?)|morphed|explicit|sexual|"
        r"video call recording|nangi)\b|"
        r"\b(?:nude|naked|morphed|obscene|intimate) (?:video|photo|pics?|images?|recording)s?\b|"
        r"\b(?:warna|nahi to|paise|payment)\b.{0,60}?\b(?:video|photos?|pics?|recording)\b"
        r".{0,40}?\b(?:bhej|viral kar|daal|post kar) ?(?:denge|dunga|doonga|dungi)\b",
        re.I | re.S,
    ),
    # Asking to rent, sell, or lend a bank account, UPI, or SIM to move other people's money
    # (SC-15).
    SignalName.MONEY_MULE_REQUEST: re.compile(
        r"\b(?:rent|lend|sell|give|share|provide|use)\b.{0,25}?\b(?:your )?(?:bank account|account|"
        r"upi(?: id)?|sim(?: card)?|current account|corporate account|account kit)\b"
        r".{0,60}?(?:\bcommission|\bper transaction|\bearn|\bincome|\bpayments?\b|\brs\b|₹|\binr\b|"
        r"\bmonthly)|"
        r"\b(?:receive|accept) (?:money|payments?|funds) (?:in|into|on) your account\b.{0,60}?"
        r"\b(?:transfer|forward|send)\b|"
        r"\baccount (?:kiraye|rent) pe\b|\bkhata kiraye\b",
        re.I | re.S,
    ),
    # Real-money gaming, betting, or "colour prediction" style apps (SC-13).
    SignalName.MONEY_GAME: re.compile(
        r"\b(?:betting|bet now|satta|matka|casino|aviator|colou?r prediction|rummy cash|"
        r"cash rummy|real money (?:game|gaming)|teen patti cash|fantasy (?:cash|winnings)|"
        r"online (?:game|gaming) (?:earn|income|winnings)|deposit (?:and|&) (?:play|win)|"
        r"game id|betting id|cricket id)\b",
        re.I,
    ),
}

_CREDENTIAL: Final = re.compile(
    rf"\b{_ASK}\b(?:\W+\w+){{0,4}}?\W+{_SECRET}\b|\b{_SECRET}\b(?:\W+\w+){{0,4}}?\W+{_ASK}\b",
    re.I,
)
_PLACEHOLDER_LINK: Final = re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|in|xyz|ly|me|example|test)\b", re.I)


_INNER_NEGATION: Final = re.compile(r"\b(?:do not|don't|dont|never|mat|nahi|nahin)\b", re.I)


def _credential_requests(text: str) -> list[re.Match[str]]:
    """Requests for secrets, excluding safety notices such as "Do not share your OTP"."""
    hits = []
    for match in _CREDENTIAL.finditer(text):
        before = text[max(0, match.start() - 30) : match.start()]
        if _NEGATION.search(before) or _INNER_NEGATION.search(match.group(0)):
            continue
        hits.append(match)
    return hits


_MONEY_SENT: Final = re.compile(
    r"\bi (?:have )?(?:already )?(?:sent|paid|transferred|deposited)\b|"
    r"\bmoney (?:was |got |has been )?(?:debited|deducted)\b|"
    r"\bmaine (?:paise|paisa|payment) (?:bhej|de|kar) di(?:ye|ya)\b|\bpaise kat gaye\b",
    re.I,
)
_CREDS_SHARED: Final = re.compile(
    rf"\bi (?:have )?(?:already )?(?:shared|gave|told|entered|sent) (?:the |my |him |her |them )?"
    rf"{_SECRET}\b|\bmaine {_SECRET} (?:bata|de|bhej) diya\b",
    re.I,
)
_LINK_CLICKED: Final = re.compile(r"\bi (?:have )?(?:already )?(?:clicked|opened|tapped)\b", re.I)
_APP_INSTALLED: Final = re.compile(
    r"\bi (?:have )?(?:already )?(?:installed|downloaded)\b|\bapp install kar (?:liya|diya)\b", re.I
)


# Child-safety screen (docs/16 section 10; POCSO Act 2012 ss.11, 19). Both a minor indicator
# and a sexual-content indicator must appear. A hit routes the case to the child-safety path
# instead of normal scam advice. Deliberately broad: missing such a case is worse than an
# extra safety message.
_MINOR: Final = re.compile(
    r"\b(?:my (?:son|daughter|child|kid|nephew|niece)|minor|school ?(?:boy|girl|student)|"
    r"(?:1[0-7]|[5-9])[ -]?(?:years?|yrs?)[ -]?old|class (?:[5-9]|1[0-2])\b|"
    r"(?:mera|meri) (?:beta|beti|bacha|bachi|baccha|bacchi)|nabalig)\b",
    re.I,
)
_SEXUAL: Final = re.compile(
    r"\b(?:nude|naked|obscene|sexual|explicit|intimate|private (?:photos?|videos?|pics?|parts?)|"
    r"morphed|porn\w*|nangi|ashleel)\b",
    re.I,
)


def detect_child_safety(text: str) -> bool:
    return bool(_MINOR.search(text) and _SEXUAL.search(text))


def detect_situation(text: str) -> dict[str, bool]:
    """What the user says has already happened (feeds the scorer's safety floors)."""
    return {
        "child_involved": detect_child_safety(text),
        "money_sent": bool(_MONEY_SENT.search(text)),
        "credentials_shared": bool(_CREDS_SHARED.search(text)),
        "link_clicked": bool(_LINK_CLICKED.search(text)),
        "app_installed": bool(_APP_INSTALLED.search(text)),
    }


def detect(masked_text: str, has_link: bool | None = None) -> list[Signal]:
    """Return at most one signal per type, each with an evidence span from the masked text."""
    signals: list[Signal] = []

    def add(name: SignalName, span: str) -> None:
        signals.append(
            Signal(
                name=name,
                confidence=RULE_CONFIDENCE,
                evidence_span=span.strip()[:80],
                evidence_id=f"S{len(signals) + 1}",
            )
        )

    credential = _credential_requests(masked_text)
    if credential:
        add(SignalName.CREDENTIAL_REQUEST, credential[0].group(0))
    for name, pattern in _RULES.items():
        match = pattern.search(masked_text)
        if match:
            add(name, match.group(0))

    link = has_link if has_link is not None else bool(_PLACEHOLDER_LINK.search(masked_text))
    if link:
        url = _PLACEHOLDER_LINK.search(masked_text)
        add(SignalName.LINK_PRESENT, url.group(0) if url else "link")
    return signals
