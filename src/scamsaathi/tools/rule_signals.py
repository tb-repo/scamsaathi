"""Rule-based behavioural signal detection (task 2.7; fallback for A2, pre-screen input).

Runs on **masked** text, so evidence spans are safe to store and show. Patterns cover
English and common romanised Hindi (Hinglish). Rules are deliberately conservative and
get a fixed, moderate confidence; the LLM extractor (Phase 4) refines them.
"""

from __future__ import annotations

import re
from typing import Any, Final

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


# Predicate / clause boundary: punctuation (including comma, colon, semicolon, dash) or conjunctions
_PREDICATE_BOUNDARY: Final = re.compile(
    r"(?:[.!?;:,\n—–-]+|\b(?:and|or|but|however|although|though|whereas|while|then|so|lekin|magar|parantu|kintu|aur|ya)\b)",
    re.I,
)

_PRE_NEG_OR_HYPO: Final = re.compile(
    r"\b(?:not|n't|never|neither|no|did not|didn't|have not|haven't|has not|hasn't|was not|wasn't|"
    r"refused|avoided|declined|without|if|what if|suppose|assuming|whether|in case|agar|yadi|kya hoga agar)\b",
    re.I,
)
_POST_NEG: Final = re.compile(r"^\W*(?:nahi|nahin|na|mat|kabhi nahi)\b|\b(?:nahi|nahin|na|mat|kabhi nahi)$", re.I)

# Routine bank transactional notice addressed in second person ("your account/card")
_BANK_TX_NOTICE: Final = re.compile(
    r"\b(?:your (?:a/c|acct|account|card|balance)|credited to your|debited from your|spent on your|"
    r"avl bal|inr\s*[\d,.]+\s*debited)\b",
    re.I,
)

_THIRD_PARTY_NOUN: Final = (
    r"(?:caller|call wale|technician|agent|officer|executive|representative|operator|scammer|fraudster|"
    r"sender|stranger|person|guy)"
)
_THIRD_PARTY_ACTOR: Final = re.compile(
    rf"\b(?:the\s+|a\s+|an\s+)?{_THIRD_PARTY_NOUN}\b|\b(?:he|she|they|usne|unhone|samne wale ne)\b",
    re.I,
)
_FIRST_PERSON_ACTOR: Final = re.compile(r"\b(?:i|i've|we|we've|maine|humne)\b", re.I)
_PREP_BEFORE: Final = re.compile(r"\b(?:to|from|with|by|for|about|at)\s+(?:the\s+|a\s+|an\s+)?$", re.I)
_POST_OBJ_HI: Final = re.compile(r"^\s*(?:ko|se|ke pass|ke sath)\b", re.I)

_THIRD_PARTY_DEVICE: Final = re.compile(
    r"\b(?:on\s+)?(?:their|his|her|its|unke|uske)\s+(?:own\s+)?(?:phone|device|mobile|screen|system|computer|laptop|handset)\b",
    re.I,
)
_SECRET_TO_USER: Final = re.compile(r"\b(?:to (?:me|us)|mujhe|mujhko)\b", re.I)

_HEARSAY_OR_UNCONFIRMED: Final = re.compile(
    r"\b(?:i\s+heard|heard\s+that|someone\s+told\s+me|i\s+was\s+told|claims?\s+that|claimed\s+that|"
    r"allegedly|rumou?r|pata\s+chala|sunne\s+me\s+aaya|kisi\s+ne\s+bataya|lagta\s+hai|might\s+have|may\s+have)\b",
    re.I,
)

_THIRD_PARTY_ACCESSED_USER_SECRET: Final = re.compile(
    rf"\b{_THIRD_PARTY_NOUN}\b.{{0,30}}?\b(?:shared|sent|used|entered|took|has|got|le\s+liya)\b.{{0,25}}?\b(?:my\s+{_SECRET}|mera\s+{_SECRET})\b|"
    rf"\b(?:my\s+{_SECRET}|mera\s+{_SECRET})\b.{{0,30}}?\b(?:was\s+shared|got\s+shared|was\s+used|was\s+sent|chala\s+gaya)\b",
    re.I,
)

_UNCONFIRMED_USER_APP: Final = re.compile(
    r"\b(?:may have|might have|suspect|think|heard)\b.{0,30}?\b(?:installed|downloaded)\b.{0,25}?\b(?:app|apk)\b|"
    rf"\b{_THIRD_PARTY_NOUN}\b.{{0,30}}?\b(?:installed|downloaded)\b.{{0,25}}?\b(?:app|apk)\b.{{0,25}}?\b(?:on my|in my|mera|meri)\b",
    re.I,
)

_UNAUTHORIZED_LOSS_CONFIRMED: Final = re.compile(
    r"\b(?:unauthorized|unauthorised|fraudulent)\s+(?:debit|transaction|transfer|deduction|withdrawal|loss)\b|"
    r"\b(?:money|amount|funds?|rupees|inr|rs\.?|₹|[\d,]+)\s+(?:was|were|got)?\s*(?:deducted|debited|taken|stolen|withdrawn|lost)\s+(?:without\s+my\s+(?:permission|consent|authorization|authorisation)|unauthorized|unauthorised)\b|"
    r"\bnoticed\s+(?:an?\s+)?(?:unauthorized|unauthorised|fraudulent)\s+(?:debit|transaction|transfer|deduction|loss)\b|"
    r"\bunauthorized\s+debit\s+appeared\b|"
    r"\bunauthorized\s+debit\b",
    re.I,
)

_TOTAL_LOSS_DENIED: Final = re.compile(
    r"\bno\s+(?:unauthorized|unauthorised)\s+(?:debit|deduction|activity|transaction|loss)\b|"
    r"\bno\s+money\s+(?:was\s+)?(?:lost|deducted|taken|stolen|debited)\b|"
    r"\bno\s+financial\s+loss\b",
    re.I,
)

_USER_TRANSFER_DENIED: Final = re.compile(
    r"\bno\s+money\s+was\s+sent\b|"
    r"\bi\s+(?:have\s+)?not\s+sent\s+(?:any\s+)?money\b|"
    r"\bi\s+haven't\s+paid\s+anything\b|"
    r"\bi\s+did\s+not\s+(?:send|pay|transfer)\b|"
    r"\bmaine\s+paise\s+nahi\s+bheje\b",
    re.I,
)

_SECRET_RECEIVED_OR_EXPOSED: Final = re.compile(
    r"\b(?:someone\s+else|third\s+party|caller|another\s+person|scammer|they|he|she)\s+(?:already\s+)?(?:received|got|has|had|knew|already\s+knew|obtained|took|entered|used|possessed|held)\b.{0,30}?\b(?:code|otp|password|pin|it)\b|"
    r"\b(?:already\s+)?(?:had|knew|obtained|got|received)\s+(?:the\s+|my\s+)?(?:code|otp|password|pin)\b|"
    r"\b(?:code|otp|password|pin)\s+(?:was\s+)?(?:already\s+)?(?:received|obtained|taken|entered|shared|known|compromised|leaked)\b|"
    r"\b(?:received|got|obtained)\s+(?:the\s+|my\s+)?(?:code|otp|password|pin)\b",
    re.I,
)

_SECRET_CONFIRMED_DENIED: Final = re.compile(
    r"\b(?:code|otp|password|pin)\s+(?:was|is)\s+not\s+for\s+my\b|"
    r"\bno\s+one\s+has\s+access\s+to\s+my\s+account\b|"
    r"\bnot\s+my\s+(?:code|otp|account)\b|"
    r"\bno\s+one\s+(?:received|obtained)\s+(?:my\s+)?(?:code|otp)\b|"
    r"\bi\s+(?:have\s+)?not\s+shared\b.{0,20}?\b(?:otp|pin|password|code|details)\b|"
    r"\bi\s+did\s+not\s+(?:share|enter|give|provide)\b.{0,20}?\b(?:otp|pin|password|code|details)\b|"
    r"\bmaine\s+otp\s+nahi\s+bataya\b|"
    r"\bno\s+one\s+(?:obtained\s+or\s+)?used\s+it\b|"
    r"\bnobody\s+used\s+it\b|"
    r"\b(?:don't|do\s+not)\s+believe\s+anyone\s+used\s+it\b|"
    r"\bdid\s+not\s+share\s+it\b|"
    r"\bno\s+one\s+obtained\s+or\s+used\b",
    re.I,
)

_APP_INSTALLED_ON_USER_DEVICE: Final = re.compile(
    r"\b(?:app|apk)\s+(?:is\s+)?on\s+my\s+(?:phone|device|mobile)\b|"
    r"\bi\s+(?:have\s+)?(?:the\s+)?(?:app|apk)\s+on\s+my\b|"
    r"\bapp\s+(?:was|is)\s+installed\s+on\s+my\b|"
    r"\binstalled\s+on\s+my\s+(?:phone|device|mobile)\b|"
    r"\bi\s+(?:have\s+)?(?:already\s+)?(?:installed|downloaded)\b.{0,20}?\b(?:app|apk)\b|"
    r"\bapp\s+install\s+kar\s+(?:liya|diya)\b",
    re.I,
)

_APP_INSTALLATION_DENIED: Final = re.compile(
    r"\bapp\s+(?:was|is)\s+not\s+installed\s+on\s+my\b|"
    r"\bnot\s+installed\s+on\s+my\s+(?:phone|device|mobile)\b|"
    r"\bi\s+did\s+not\s+install\s+(?:it|the\s+app|any\s+app|apk)\b|"
    r"\bon\s+the\s+(?:technician's|caller's|other\s+person's)\s+own\s+phone\b",
    re.I,
)

_THIRD_PARTY_INSTALLED_APP: Final = re.compile(
    r"\b(?:someone\s+else|third\s+party|caller|another\s+person|scammer|technician|agent|executive|stranger|they|he|she)\s+(?:already\s+)?(?:installed|downloaded|put|sideloaded)\b|"
    r"\b(?:installed|downloaded|put|sideloaded)\s+by\s+(?:the\s+)?(?:technician|caller|scammer|executive|agent|third\s+party|someone\s+else)\b",
    re.I,
)

_REMOTE_ACCESS_DENIED: Final = re.compile(
    r"\b(?:granted|gave)\s+no\s+remote\s+access\b|"
    r"\bno\s+remote\s+access\s+was\s+granted\b|"
    r"\bdid\s+not\s+grant\s+(?:any\s+)?(?:remote\s+access|permissions?)\b|"
    r"\bno\s+permissions?\s+(?:given|granted)\b|"
    r"\bwithout\s+(?:my\s+)?(?:asking|permission|consent|knowledge|authorization|authorisation)\b|"
    r"\bwithout\s+asking\s+me\b|"
    r"\bunauthorized\b",
    re.I,
)

_REMOTE_ACCESS_GRANTED: Final = re.compile(
    r"\b(?:granted|gave|allowed)\s+(?:remote\s+access|permissions?)\b|"
    r"\bwith\s+permissions\b|"
    r"\bshared\s+(?:the\s+)?(?:access\s+code|screen)\b",
    re.I,
)

# First-person money sent or loss: user reporting money left *their* account or they transferred/sent it
_MONEY_SENT: Final = re.compile(
    r"\bi (?:have )?(?:already )?(?:sent|paid|transferred|deposited)\b|"
    r"\b(?:(?:₹|rs\.?|inr|\$)?\s*[\d,]+|money|amount|funds?)\b.{0,30}?\b(?:left|gone from|taken from|stolen from|cut from|debited from|deducted from)\b.{0,15}?\b(?:my account|my bank)\b|"
    r"\b(?:left|gone|taken|debited|deducted)\b.{0,20}?\bfrom my account\b|"
    r"\bmaine (?:paise|paisa|payment) (?:bhej|de|kar) di(?:ye|ya)\b|\bpaise kat gaye\b|"
    r"\b(?:account se|paise|paisa)\b.{0,30}?\b(?:cut|kat)\b.{0,15}?\b(?:gaye|gaya|hone|ho gaya)\b",
    re.I,
)
_CREDS_SHARED: Final = re.compile(
    rf"\b(?:did share|shared|gave|told|entered|sent|provided|typed in)\b.{{0,25}}?\b{_SECRET}\b|"
    rf"\b(?:did share|shared|gave|told|provided)\b.{{0,20}}?\bit\b.{{0,25}}?\b(?:with|to)\b.{{0,10}}?\b(?:the )?(?:caller|him|her|them|scammer|fraudster)\b|"
    rf"\b(?:entered|typed in)\b.{{0,15}}?\bit\b|"
    rf"\bmaine\b.{{0,60}}?\b{_SECRET}\b.{{0,20}}?\b(?:bata|de|bhej|enter kar|daal) di(?:ya|ye)\b",
    re.I | re.S,
)
_LINK_CLICKED: Final = re.compile(
    r"\b(?:clicked|opened|tapped|followed|visited)\b.{0,25}?(?:link|url|website|site|portal)\b|"
    r"\bi (?:have )?(?:already )?(?:clicked|opened|tapped|followed|visited)\b|"
    r"\blink (?:par|pe) (?:click|open|tap) kiya\b",
    re.I,
)
_APP_INSTALLED: Final = re.compile(
    r"\b(?:installed|downloaded)\b.{0,25}?(?:app|apk)\b|"
    r"\bi (?:have )?(?:already )?(?:installed|downloaded)\b|\bapp install kar (?:liya|diya)\b",
    re.I,
)


def _get_predicate_bounds(text: str, match_start: int, match_end: int) -> tuple[int, int]:
    """Find the start and end of the predicate containing the match without crossing clause boundaries."""
    pred_start = 0
    for b in _PREDICATE_BOUNDARY.finditer(text[:match_start]):
        pred_start = b.end()
    pred_end = len(text)
    m = _PREDICATE_BOUNDARY.search(text[match_end:])
    if m:
        pred_end = match_end + m.start()
    return pred_start, pred_end


def _is_third_party_actor(text: str, pred_start: int, match_start: int) -> bool:
    """Check if the subject performing the action is a third party rather than the user."""
    before_in_pred = text[pred_start:match_start]
    last_first_pos = -1
    for m in _FIRST_PERSON_ACTOR.finditer(before_in_pred):
        last_first_pos = max(last_first_pos, m.end())

    last_third_pos = -1
    for m in _THIRD_PARTY_ACTOR.finditer(before_in_pred):
        pre = before_in_pred[:m.start()]
        post = before_in_pred[m.end():]
        if _PREP_BEFORE.search(pre) or _POST_OBJ_HI.search(post):
            continue
        last_third_pos = max(last_third_pos, m.end())

    if last_third_pos > last_first_pos:
        return True
    if last_first_pos >= 0:
        return False

    # If the current predicate starts after a coordinating conjunction (like 'and'),
    # inspect the preceding clause for the subject.
    if pred_start > 0:
        preceding = text[:pred_start].strip()
        p_start = 0
        for b in _PREDICATE_BOUNDARY.finditer(preceding):
            p_start = b.end()
        preceding_clause = preceding[p_start:]
        if _FIRST_PERSON_ACTOR.search(preceding_clause):
            return False
        for m in _THIRD_PARTY_ACTOR.finditer(preceding_clause):
            pre = preceding_clause[:m.start()]
            post = preceding_clause[m.end():]
            if _PREP_BEFORE.search(pre):
                continue
            if _POST_OBJ_HI.search(post):
                continue
            return True
    return False


def _is_negated_or_hypothetical(text: str, match: re.Match[str]) -> bool:
    """Check for negations or hypotheticals strictly within the same predicate as the match."""
    start, end = match.start(), match.end()
    pred_start, pred_end = _get_predicate_bounds(text, start, end)
    before_in_pred = text[pred_start:start]
    after_in_pred = text[end:pred_end]
    matched_text = match.group(0)

    if _PRE_NEG_OR_HYPO.search(before_in_pred):
        return True
    if _PRE_NEG_OR_HYPO.search(matched_text):
        return True
    if _POST_NEG.search(after_in_pred):
        return True
    return False


def _check_money_sent(text: str) -> bool:
    # 1. If an unauthorized debit or fraudulent loss is confirmed in an un-negated clause:
    # That is confirmed financial loss, even if user clarifies "no money was sent by me".
    for m in _UNAUTHORIZED_LOSS_CONFIRMED.finditer(text):
        if not _is_negated_or_hypothetical(text, m):
            return True

    # 2. If the user explicitly denies any financial loss or unauthorized debit:
    if _TOTAL_LOSS_DENIED.search(text):
        return False

    # 3. If the user denies sending money and no unauthorized debit was reported:
    if _USER_TRANSFER_DENIED.search(text):
        return False

    # 4. Standard first-person money transfer detection:
    for m in _MONEY_SENT.finditer(text):
        if not _is_negated_or_hypothetical(text, m):
            return True

    return False


def _check_creds_shared(text: str) -> bool:
    for m in _CREDS_SHARED.finditer(text):
        if _is_negated_or_hypothetical(text, m):
            continue
        pred_start, pred_end = _get_predicate_bounds(text, m.start(), m.end())
        after_in_pred = text[m.end():pred_end]
        if _SECRET_TO_USER.search(after_in_pred) or _SECRET_TO_USER.search(m.group(0)):
            continue
        if _is_third_party_actor(text, pred_start, m.start()):
            continue
        return True
    return False


def _check_link_clicked(text: str) -> bool:
    for m in _LINK_CLICKED.finditer(text):
        if _is_negated_or_hypothetical(text, m):
            continue
        pred_start, pred_end = _get_predicate_bounds(text, m.start(), m.end())
        pred_text = text[pred_start:pred_end]
        if _THIRD_PARTY_DEVICE.search(pred_text):
            continue
        if _is_third_party_actor(text, pred_start, m.start()):
            continue
        return True
    return False


def _check_app_installed(text: str) -> bool:
    for m in _APP_INSTALLED.finditer(text):
        if _is_negated_or_hypothetical(text, m):
            continue
        pred_start, pred_end = _get_predicate_bounds(text, m.start(), m.end())
        pred_text = text[pred_start:pred_end]
        if _THIRD_PARTY_DEVICE.search(pred_text):
            continue
        if _is_third_party_actor(text, pred_start, m.start()):
            continue
        return True
    return False


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


_HEARSAY_MONEY: Final = re.compile(
    r"\b(?:money|funds?|cash|amount|paise|paisa|rupees|inr|rs\.?|₹)\b.{0,30}?\b(?:lost|gone|deducted|debited|taken|transferred|stolen)\b|"
    r"\b(?:unauthorized|unauthorised|suspicious)\s+(?:debit|deduction|transfer|transaction|loss)\b|"
    r"\b(?:loss|deduction|debit)\s+of\s+money\b",
    re.I,
)


def detect_situation(text: str) -> dict[str, Any]:
    """What the user says has already happened (feeds the scorer's safety floors and interview)."""
    child_safety = detect_child_safety(text)
    money_sent = _check_money_sent(text)
    link_clicked = _check_link_clicked(text)

    uncertainties: list[str] = []
    creds_exp: dict[str, Any] | None = None
    app_exp: dict[str, Any] | None = None
    money_exp: dict[str, Any] | None = None

    # 1. Credentials exposure determination:
    # Distinguish received/exposed, confirmed denied, and unresolved/unknown
    if _SECRET_RECEIVED_OR_EXPOSED.search(text) or _check_creds_shared(text):
        creds_exp = {"status": "confirmed", "actor": "third_party", "target": "user_account"}
        credentials_shared = True
    elif _SECRET_CONFIRMED_DENIED.search(text):
        creds_exp = {"status": "denied", "actor": "user", "target": "user_account"}
        credentials_shared = False
    elif _THIRD_PARTY_ACCESSED_USER_SECRET.search(text) or (
        _HEARSAY_OR_UNCONFIRMED.search(text) and re.search(rf"\b(?:my\s+{_SECRET}|mera\s+{_SECRET}|{_SECRET})\b", text, re.I)
    ):
        creds_exp = {"status": "unknown", "actor": "third_party", "target": "user_account"}
        credentials_shared = False
        uncertainties.append("otp_account_exposure")
    else:
        credentials_shared = False

    # 2. App installation determination:
    # Decouple installation on device from remote access permissions
    app_installed_on_user = bool(_APP_INSTALLED_ON_USER_DEVICE.search(text) or _check_app_installed(text))
    app_install_denied = bool(_APP_INSTALLATION_DENIED.search(text))
    remote_denied = bool(_REMOTE_ACCESS_DENIED.search(text))
    remote_granted = bool(_REMOTE_ACCESS_GRANTED.search(text))

    if app_installed_on_user:
        app_installed = True
        auth_status = "denied" if remote_denied else ("confirmed" if remote_granted else "unknown")
        actor_type = "third_party" if _THIRD_PARTY_INSTALLED_APP.search(text) else "user"
        app_exp = {"status": "confirmed", "actor": actor_type, "target": "user_device", "authorized": auth_status}
    elif app_install_denied:
        app_installed = False
        auth_status = "denied" if remote_denied else "unknown"
        app_exp = {"status": "denied", "actor": "user", "target": "user_device", "authorized": auth_status}
    elif _UNCONFIRMED_USER_APP.search(text) or (
        _HEARSAY_OR_UNCONFIRMED.search(text) and re.search(r"\b(?:app|apk)\b", text, re.I)
    ):
        app_installed = False
        auth_status = "denied" if remote_denied else ("confirmed" if remote_granted else "unknown")
        app_exp = {"status": "unknown", "actor": "third_party", "target": "user_device", "authorized": auth_status}
        uncertainties.append("apk_device_exposure")
    else:
        app_installed = False

    # 3. Money loss determination
    if money_sent:
        is_unauth = bool(_UNAUTHORIZED_LOSS_CONFIRMED.search(text))
        money_exp = {
            "status": "confirmed",
            "actor": "user",
            "target": "user_account",
            "authorized": "denied" if is_unauth else "confirmed",
        }
    elif _TOTAL_LOSS_DENIED.search(text) or _USER_TRANSFER_DENIED.search(text):
        money_exp = {"status": "denied", "actor": "user", "target": "user_account", "authorized": "unknown"}
        money_sent = False
    elif _HEARSAY_MONEY.search(text) and _HEARSAY_OR_UNCONFIRMED.search(text):
        money_exp = {"status": "unknown", "actor": "user", "target": "user_account", "authorized": "unknown"}
        uncertainties.append("unauthorized_loss_noticed")

    res: dict[str, Any] = {
        "child_involved": child_safety,
        "money_sent": money_sent,
        "credentials_shared": credentials_shared,
        "link_clicked": link_clicked,
        "app_installed": app_installed,
    }
    if creds_exp is not None:
        res["credentials_exposure"] = creds_exp
    if app_exp is not None:
        res["app_installation"] = app_exp
    if money_exp is not None:
        res["money_loss"] = money_exp
    if uncertainties:
        res["unresolved_uncertainties"] = uncertainties

    return res


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
