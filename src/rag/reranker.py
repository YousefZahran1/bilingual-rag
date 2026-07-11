"""Cross-encoder re-ranker: re-scores a fused candidate list, top-N -> top-k.

Model default is a light multilingual MiniLM cross-encoder
(cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), not BAAI/bge-reranker-v2-m3.
bge-reranker-v2-m3 is an XLM-R-large checkpoint (~2.2GB) -- meaningfully
heavier than everything else in this stack. This project already made a
deliberate small-model choice once (multilingual-e5-small over larger e5
variants); the MiniLM cross-encoder keeps that size:quality philosophy
consistent instead of bolting a 2GB model onto an otherwise "small and free"
pipeline. bge-reranker-v2-m3 is documented as a named stretch upgrade in
docs/ROADMAP.md.

Lazy-loaded like VectorStore: the model name is stored in __init__, the
actual sentence_transformers.CrossEncoder(...) is constructed on first use
(or via .warm(), used to pre-load the model at Docker build time).
"""
from __future__ import annotations

import os
from typing import List

from .store import RetrievedPassage

DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class CrossEncoderReranker:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.environ.get("RERANKER_MODEL", DEFAULT_MODEL)
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # noqa: WPS433

            self._model = CrossEncoder(self.model_name)
        return self._model

    def warm(self) -> None:
        """Force model construction/download. Used to bake the model into
        the Docker image at build time instead of lazy-loading it on the
        first live /chat request in production."""
        self._get_model()

    def rerank(
        self, query: str, passages: List[RetrievedPassage], top_k: int = 4
    ) -> List[RetrievedPassage]:
        if not passages:
            return []
        model = self._get_model()
        pairs = [(query, p.text) for p in passages]
        scores = model.predict(pairs)
        scored = list(zip(passages, scores))
        scored.sort(key=lambda item: item[1], reverse=True)
        reranked = []
        for passage, score in scored[:top_k]:
            reranked.append(
                RetrievedPassage(
                    text=passage.text,
                    source=passage.source,
                    chunk_id=passage.chunk_id,
                    language=passage.language,
                    score=passage.score,
                    rerank_score=float(score),
                )
            )
        return reranked
