"""Language detection unit tests."""
from src.rag.lang import detect_language


def test_pure_english():
    assert detect_language("This is a clearly English sentence.") == "en"


def test_pure_arabic():
    assert detect_language("هذه جملة عربية واضحة تمامًا.") == "ar"


def test_mixed_text():
    # 10 Arabic chars (مرحبا x2) vs 10 ASCII letters (Hello x2) → ratio_ar=0.5 → "mixed"
    assert detect_language("Hello مرحبا Hello مرحبا.") == "mixed"


def test_empty():
    assert detect_language("") == "en"
    assert detect_language("   \n  ") == "en"


def test_digits_and_punct_only():
    # No letters at all -> default 'en'
    assert detect_language("12345 !!!") == "en"
