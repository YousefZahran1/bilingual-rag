"""normalize_arabic / tokenize edge cases for BM25 indexing."""
from src.rag.lang import normalize_arabic, tokenize


def test_normalize_strips_diacritics():
    assert normalize_arabic("الْحَدُّ") == "الحد"


def test_normalize_strips_tatweel():
    assert normalize_arabic("سـلام") == "سلام"


def test_normalize_unifies_alef_variants():
    assert normalize_arabic("إأآ") == "ااا"


def test_normalize_unifies_taa_marbuta_and_alef_maqsura():
    assert normalize_arabic("مدرسة") == "مدرسه"
    assert normalize_arabic("على") == "علي"


def test_tokenize_preserves_numbers():
    tokens = tokenize("The cap is SAR 1500 per day.")
    assert "1500" in tokens


def test_tokenize_lowercases_and_splits_arabic():
    tokens = tokenize("السقف اليومي هو 1500 ريال")
    assert tokens == ["السقف", "اليومي", "هو", "1500", "ريال"]


def test_tokenize_empty_string():
    assert tokenize("") == []


def test_tokenize_does_not_strip_attached_affixes():
    # Documented limitation: light normalization, not stemming.
    assert tokenize("والتأمين") == ["والتامين"]
    assert tokenize("التأمين") == ["التامين"]
