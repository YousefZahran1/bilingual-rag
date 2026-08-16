"""Minimal langchain_core.embeddings.Embeddings wrapper around this
project's own multilingual-e5 model, so eval/run_ragas.py's context_recall/
context_precision/answer_relevancy metrics embed with the same model the
retrieval pipeline itself uses -- no separate embeddings API/cost needed
for that part of the judge (only the LLM judge calls themselves cost
anything). Mirrors the "query: "/"passage: " prefix convention already
used in src/rag/store.py and src/rag/pipeline.py.
"""
from __future__ import annotations

import os

from langchain_core.embeddings import Embeddings

EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")


class E5Embeddings(Embeddings):
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(EMBED_MODEL)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode([f"passage: {t}" for t in texts]).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode(f"query: {text}").tolist()
