"""CrossEncoderReranker.rerank() sorts and truncates by score. No live model."""
from src.rag.reranker import CrossEncoderReranker
from src.rag.store import RetrievedPassage


class FakeCrossEncoder:
    def __init__(self, scores):
        self._scores = scores
        self.calls = []

    def predict(self, pairs):
        self.calls.append(pairs)
        return self._scores


def _passages():
    return [
        RetrievedPassage(text="low relevance", source="a.md", chunk_id=0, language="en", score=0.5),
        RetrievedPassage(text="high relevance", source="b.md", chunk_id=0, language="en", score=0.4),
        RetrievedPassage(text="mid relevance", source="c.md", chunk_id=0, language="en", score=0.6),
    ]


def test_rerank_sorts_by_cross_encoder_score():
    reranker = CrossEncoderReranker()
    reranker._model = FakeCrossEncoder(scores=[0.1, 0.9, 0.5])

    result = reranker.rerank("query", _passages(), top_k=3)

    assert [p.source for p in result] == ["b.md", "c.md", "a.md"]


def test_rerank_truncates_to_top_k():
    reranker = CrossEncoderReranker()
    reranker._model = FakeCrossEncoder(scores=[0.1, 0.9, 0.5])

    result = reranker.rerank("query", _passages(), top_k=1)

    assert len(result) == 1
    assert result[0].source == "b.md"


def test_rerank_preserves_original_score_and_sets_rerank_score():
    reranker = CrossEncoderReranker()
    reranker._model = FakeCrossEncoder(scores=[0.1, 0.9, 0.5])

    result = reranker.rerank("query", _passages(), top_k=3)

    top = result[0]
    assert top.score == 0.4  # original dense/RRF score untouched
    assert top.rerank_score == 0.9


def test_rerank_empty_passages_returns_empty():
    reranker = CrossEncoderReranker()
    reranker._model = FakeCrossEncoder(scores=[])
    assert reranker.rerank("query", [], top_k=4) == []


def test_get_model_only_called_when_model_unset(monkeypatch):
    reranker = CrossEncoderReranker()
    reranker._model = FakeCrossEncoder(scores=[1.0])

    def fail_import():
        raise AssertionError("should not construct a real model")

    monkeypatch.setattr(reranker, "_get_model", lambda: reranker._model if reranker._model else fail_import())
    result = reranker.rerank("q", [_passages()[0]], top_k=1)
    assert result[0].source == "a.md"
