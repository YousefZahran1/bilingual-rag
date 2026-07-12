"""reciprocal_rank_fusion correctness on hand-built rankings, and
retrieve_pipeline wiring with fake store/bm25/reranker doubles (no live
models)."""
from src.rag.fusion import reciprocal_rank_fusion, retrieve_pipeline, smart_retrieve
from src.rag.store import RetrievedPassage


def test_doc_ranked_first_in_two_lists_beats_doc_ranked_first_in_one():
    dense = ["a", "b", "c"]
    sparse = ["a", "c", "b"]
    fused = reciprocal_rank_fusion([dense, sparse])
    fused_ids = [doc_id for doc_id, _ in fused]
    assert fused_ids[0] == "a"


def test_fusion_formula_matches_manual_computation():
    dense = ["a", "b"]
    sparse = ["b", "a"]
    fused = dict(reciprocal_rank_fusion([dense, sparse], k=60))
    assert fused["a"] == 1 / 61 + 1 / 62
    assert fused["b"] == 1 / 62 + 1 / 61


def test_doc_missing_from_one_ranking_still_scored():
    dense = ["a", "b"]
    sparse = ["c"]
    fused = dict(reciprocal_rank_fusion([dense, sparse], k=60))
    assert fused["a"] == 1 / 61
    assert fused["c"] == 1 / 61


def test_empty_rankings_returns_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_results_sorted_descending():
    fused = reciprocal_rank_fusion([["x", "y", "z"]])
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)


class FakeStore:
    def __init__(self, passages):
        self._passages = passages
        self.calls = []

    def retrieve(self, query, top_k=4):
        self.calls.append((query, top_k))
        return self._passages[:top_k]


class FakeBM25:
    def __init__(self, passages):
        self._passages = passages
        self.calls = []

    def search(self, query, top_k=4):
        self.calls.append((query, top_k))
        return self._passages[:top_k]


class FakeReranker:
    def __init__(self):
        self.calls = []

    def rerank(self, query, passages, top_k=4):
        self.calls.append((query, passages, top_k))
        return passages[:top_k]


def _passage(source, chunk_id=0, score=0.5):
    return RetrievedPassage(text=f"text-{source}", source=source, chunk_id=chunk_id, language="en", score=score)


def test_retrieve_pipeline_fuses_dense_and_sparse_then_reranks():
    dense = [_passage("a.md"), _passage("b.md")]
    sparse = [_passage("b.md"), _passage("c.md")]
    store = FakeStore(dense)
    bm25 = FakeBM25(sparse)
    reranker = FakeReranker()

    result = retrieve_pipeline("query", store, bm25, reranker, top_k=2, fusion_top_n=20)

    # b.md appears in both rankings -> should be the top fused candidate,
    # and reranker should have been called with the deduped fused set.
    fused_sources = [p.source for p in reranker.calls[0][1]]
    assert fused_sources[0] == "b.md"
    assert set(fused_sources) == {"a.md", "b.md", "c.md"}
    assert result == reranker.calls[0][1][:2]


def test_retrieve_pipeline_calls_reranker_with_top_k():
    store = FakeStore([_passage("a.md")])
    bm25 = FakeBM25([])
    reranker = FakeReranker()

    retrieve_pipeline("query", store, bm25, reranker, top_k=1, fusion_top_n=20)

    assert reranker.calls[0][2] == 1


def test_smart_retrieve_routes_numeric_query_to_bm25_only():
    store = FakeStore([_passage("a.md")])
    bm25 = FakeBM25([_passage("b.md")])
    reranker = FakeReranker()

    result = smart_retrieve("How many dental cleanings are covered per year?", store, bm25, reranker, top_k=4)

    assert bm25.calls
    assert not store.calls
    assert not reranker.calls
    assert [p.source for p in result] == ["b.md"]


def test_smart_retrieve_routes_non_numeric_query_to_hybrid_rerank():
    store = FakeStore([_passage("a.md")])
    bm25 = FakeBM25([_passage("a.md")])
    reranker = FakeReranker()

    smart_retrieve("Does this plan cover veterinary care for my pet?", store, bm25, reranker, top_k=4)

    assert store.calls
    assert reranker.calls
