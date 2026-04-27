"""Lightweight Arabic / English / mixed detection.

We avoid pulling langdetect for a 2-language task. Range checks on the
Unicode Arabic block are sufficient and far faster.
"""
from __future__ import annotations

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
