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
