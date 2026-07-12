"""Pure-function tests for eval/run_eval.py's scoring helpers.

No real retrieval call -- these test expected-source normalization, basename
extraction, and abstain-phrase detection in isolation.
"""
from eval.run_eval import _basenames, _expected_sources, _looks_like_abstain
from src.rag.store import RetrievedPassage


def test_expected_sources_prefers_plural_field():
    item = {"expected_source": "a.md", "expected_sources": ["b.md", "c.md"]}
    assert _expected_sources(item) == ["b.md", "c.md"]


def test_expected_sources_falls_back_to_singular_field():
    item = {"expected_source": "a.md"}
    assert _expected_sources(item) == ["a.md"]


def test_expected_sources_empty_when_neither_present():
    assert _expected_sources({}) == []


def test_basenames_extracts_filename_regardless_of_path_separator():
    passages = [
        RetrievedPassage(text="t", source="sample/01_health_plan_en.md", chunk_id=0, language="en", score=0.9),
        RetrievedPassage(text="t", source="sample\\02_health_plan_ar.md", chunk_id=0, language="ar", score=0.8),
    ]
    assert _basenames(passages) == ["01_health_plan_en.md", "02_health_plan_ar.md"]


def test_looks_like_abstain_detects_english_marker():
    assert _looks_like_abstain("Sorry, I don't know based on the passages.")


def test_looks_like_abstain_detects_arabic_marker():
    assert _looks_like_abstain("عذرًا، لا أعرف الإجابة.")


def test_looks_like_abstain_false_for_confident_answer():
    assert not _looks_like_abstain("The daily room cap is SAR 1,500.")


def test_looks_like_abstain_handles_curly_apostrophe():
    # Regression test: openai/gpt-oss-20b:free consistently uses U+2019 in
    # contractions ("isn't", "can't"), which silently missed ASCII-apostrophe
    # markers on the first real run -- 17/17 genuine refusals scored as 0/17.
    assert _looks_like_abstain("I’m sorry, but that information isn’t provided in the passages.")
    assert _looks_like_abstain("I’m sorry, but I can’t provide that information.")
    assert _looks_like_abstain("I’m sorry, but I can’t comply with that.")


def test_looks_like_abstain_detects_laa_aalam_variant():
    # لا أعلم (I don't know) vs لا أعرف -- different word, both valid Arabic.
    assert _looks_like_abstain("لا أعلم.")


def test_looks_like_abstain_detects_whether_phrasing():
    # "does not indicate whether X is covered" -- a softer refusal form the
    # marker list initially missed (only had "...indicate THAT").
    assert _looks_like_abstain(
        "I’m sorry, but the information provided does not indicate whether "
        "veterinary care for pets is covered by the plan."
    )


def test_looks_like_abstain_detects_further_real_phrasing_variants():
    # More real refusal phrasings caught across the three-mode real-LLM
    # eval run: "isn't available in" / "not mentioned in" / لا أستطيع.
    assert _looks_like_abstain("I’m sorry, but that information isn’t available in the provided passages.")
    assert _looks_like_abstain("The payout amount is not mentioned in the provided passages.")
    assert _looks_like_abstain("عذرًا، لا أستطيع المساعدة في ذلك.")
