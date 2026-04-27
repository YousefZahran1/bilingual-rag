"""Generator wired to MockProvider produces a non-empty answer with citations."""
import os

from src.rag.generator import generate
from src.rag.store import RetrievedPassage


def test_mock_generator_returns_answer_and_citations(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    passages = [
        RetrievedPassage(
            text="The daily room cap is SAR 1,500 for shared rooms.",
            source="01_health_plan_en.md",
            chunk_id=0,
            language="en",
            score=0.91,
        )
    ]
    result = generate("What is the daily room cap?", passages)
    assert result.answer
    assert len(result.citations) == 1
    assert result.citations[0]["source"] == "01_health_plan_en.md"
    assert result.language == "en"


def test_mock_generator_arabic_question(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    passages = [
        RetrievedPassage(
            text="سقف الغرفة اليومية 1500 ريال.",
            source="02_health_plan_ar.md",
            chunk_id=0,
            language="ar",
            score=0.88,
        )
    ]
    result = generate("ما هو سقف الغرفة اليومية؟", passages)
    assert result.language == "ar"
    assert result.citations[0]["source"] == "02_health_plan_ar.md"
