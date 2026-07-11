"""Lightweight Arabic / English / mixed detection.

We avoid pulling langdetect for a 2-language task. Range checks on the
Unicode Arabic block are sufficient and far faster.
"""
from __future__ import annotations

import re

ARABIC_RANGES = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)


def is_arabic_char(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in ARABIC_RANGES)


def detect_language(text: str) -> str:
    """Return 'ar', 'en', or 'mixed'.

    Heuristic: count Arabic letter chars vs ASCII letter chars (ignore digits,
    punctuation, whitespace). >70% Arabic -> 'ar'; >70% ASCII letters -> 'en';
    otherwise 'mixed'.
    """
    if not text:
        return "en"
    ar = sum(1 for c in text if is_arabic_char(c))
    en = sum(1 for c in text if "a" <= c.lower() <= "z")
    total = ar + en
    if total == 0:
        return "en"
    ratio_ar = ar / total
    if ratio_ar >= 0.7:
        return "ar"
    if ratio_ar <= 0.3:
        return "en"
    return "mixed"


# --- BM25 tokenization helpers ---
#
# This is light normalization, not stemming: it strips diacritics/tatweel and
# unifies a few letter variants, but it does NOT strip attached Arabic
# prefixes (ال، و، ف، ب، ك، ل) or suffixes (ها، هم، كم، ...). "والتأمين" and
# "التأمين" remain different tokens. A real system would use a proper
# morphological analyzer (e.g. CAMeL Tools); this is intentionally simple.

_DIACRITICS = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ۭ]"
)
_TATWEEL = "ـ"
_ALEF_VARIANTS = str.maketrans(
    {
        "إ": "ا",  # إ -> ا
        "أ": "ا",  # أ -> ا
        "آ": "ا",  # آ -> ا
        "ة": "ه",  # ة -> ه
        "ى": "ي",  # ى -> ي
    }
)

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def normalize_arabic(text: str) -> str:
    """Strip diacritics/tatweel and unify common letter variants."""
    text = _DIACRITICS.sub("", text)
    text = text.replace(_TATWEEL, "")
    return text.translate(_ALEF_VARIANTS)


def tokenize(text: str) -> list[str]:
    """Normalize + lowercase + split into word tokens for BM25 indexing.

    Numbers are kept as tokens deliberately: exact numeric matching (SAR
    figures, percentages, day-counts) is BM25's main value-add over dense
    embeddings, which tend to blur numeric detail.
    """
    normalized = normalize_arabic(text).lower()
    return _TOKEN_PATTERN.findall(normalized)
