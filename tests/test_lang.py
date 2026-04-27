"""Language detection unit tests."""
from src.rag.lang import detect_language


def test_pure_english():
    assert detect_language("This is a clearly English sentence.") == "en"


def test_pure_arabic():
    assert detect_language("هذه جملة عربية واضحة تمامًا.") == "ar"


def test_mixed_text():
    assert detect_language("Hello and مرحبا — fifty-fifty mix here.") == "mixed"


def test_empty():
    assert detect_language("") == "en"
    assert detect_language("   \n  ") == "en"


def test_digits_and_punct_only():
    # No letters at all -> default 'en'
    assert detect_language("12345 !!!") == "en"
