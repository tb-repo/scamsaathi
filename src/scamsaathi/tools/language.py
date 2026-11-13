"""Language detection for English, Hinglish, and Hindi (task 2.2, FR-002).

Script ratios separate Devanagari Hindi and other Indian scripts; a romanised-Hindi
lexicon separates Hinglish from English. Low-confidence cases can be escalated to the
LLM by the intake agent (Phase 4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from scamsaathi.schemas import Language

# Common romanised Hindi function words and scam-context words. Kept to words that are
# rare in English so that ordinary English text does not trip the detector.
_HINGLISH: Final = frozenset(
    """
    aap aapka aapki aapke apna apni apne hai hain tha thi hoga hogi hoge ho jayega jayegi
    karein karo kare karna kariye kijiye kiya kiye nahi nahin mat kya kyun kaise kab kahan
    mein mai main hum humko mujhe tum tumhara yeh ye woh wo isko usko inko unko
    hoon hu aur kisi naam rahiye bol bolta bolti
    turant jaldi abhi warna varna paisa paise rupaye khata band bhejo bhejiye bhej diya
    raha rahe rahi wala wali wale sirf bas bhai beta ji haan accha theek liye dijiye lijiye
    batao bataiye boliye bolo samjhe chahiye milega milegi dena lena sakte sakta sakti
    """.split()
)
_WORD_RE: Final = re.compile(r"[a-zA-Z]+")


@dataclass(frozen=True)
class LanguageResult:
    language: Language
    confidence: float


def _script_counts(text: str) -> tuple[int, int, int]:
    """Return (latin letters, Devanagari letters, other-script letters)."""
    latin = devanagari = other = 0
    for char in text:
        if not char.isalpha():
            continue
        code = ord(char)
        if char.isascii():
            latin += 1
        elif 0x0900 <= code <= 0x097F:
            devanagari += 1
        else:
            other += 1
    return latin, devanagari, other


def detect(text: str) -> LanguageResult:
    latin, devanagari, other = _script_counts(text)
    letters = latin + devanagari + other
    if letters == 0:
        return LanguageResult(Language.OTHER, 0.0)

    if devanagari / letters >= 0.5:
        return LanguageResult(Language.HI, round(devanagari / letters, 2))
    if other / letters >= 0.5:
        return LanguageResult(Language.OTHER, round(other / letters, 2))

    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return LanguageResult(Language.OTHER, 0.0)
    hits = sum(1 for w in words if w in _HINGLISH)
    ratio = hits / len(words)
    if hits >= 2 and ratio >= 0.12:
        return LanguageResult(Language.HINGLISH, round(min(1.0, 0.5 + ratio), 2))
    if hits == 0:
        return LanguageResult(Language.EN, 0.9 if len(words) >= 4 else 0.6)
    # One stray Hindi word in English text: lean English, low confidence.
    return LanguageResult(Language.EN, 0.55)
