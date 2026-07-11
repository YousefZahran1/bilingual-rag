"""Reciprocal Rank Fusion for combining dense + sparse retrieval rankings,
plus the hybrid retrieve -> rerank pipeline built on top of it."""
from __future__ import annotations

from typing import List, Tuple

from .bm25_index import BM25Index
from .reranker import CrossEncoderReranker
from .store import RetrievedPassage, VectorStore


def reciprocal_rank_fusion(
    rankings: List[List[str]],
    k: int = 60,
) -> List[Tuple[str, float]]:
    """Fuse multiple rankings of doc ids into one score-sorted ranking.

    Each inner list in `rankings` is a list of doc ids in rank order (best
    first). A doc's fused score is the sum over every ranking that contains
    it of 1 / (k + rank), using a 1-indexed rank. k=60 is the constant from
    the original Cormack et al. RRF paper -- used as-is rather than tuned
    against this project's own eval set, since tuning a hyperparameter
    against a small self-authored eval set and then citing the resulting
    number is a credibility risk.

    Returns (doc_id, fused_score) pairs sorted by score descending.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def _doc_id(passage: RetrievedPassage) -> str:
    return f"{passage.source}::{passage.chunk_id}"


def retrieve_pipeline(
    query: str,
    store: VectorStore,
    bm25_index: BM25Index,
    reranker: CrossEncoderReranker,
    top_k: int = 4,
    fusion_top_n: int = 20,
) -> List[RetrievedPassage]:
    """Dense top-N + BM25 top-N -> RRF fuse -> top-N fused candidates ->
    cross-encoder rerank -> top_k. VectorStore.retrieve() itself stays
    dense-only and is used elsewhere as the explicit "before" comparison
    arm; this function is the new default retrieval path."""
    dense = store.retrieve(query, top_k=fusion_top_n)
    sparse = bm25_index.search(query, top_k=fusion_top_n)

    by_id = {_doc_id(p): p for p in [*dense, *sparse]}
    fused = reciprocal_rank_fusion(
        [[_doc_id(p) for p in dense], [_doc_id(p) for p in sparse]]
    )

    candidates = [
        RetrievedPassage(
            text=by_id[doc_id].text,
            source=by_id[doc_id].source,
            chunk_id=by_id[doc_id].chunk_id,
            language=by_id[doc_id].language,
            score=fused_score,
        )
        for doc_id, fused_score in fused[:fusion_top_n]
    ]

    return reranker.rerank(query, candidates, top_k=top_k)
