"""Chroma persistent store wrapper.

Defers heavy imports to first call so the rest of the package stays importable
in environments where chromadb / sentence-transformers aren't installed
(e.g., during early CI).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from .chunker import Chunk

DEFAULT_COLLECTION = "bilingual_rag"


@dataclass
class RetrievedPassage:
    text: str
    source: str
    chunk_id: int
    language: str
    score: float


class VectorStore:
    def __init__(
        self,
        persist_dir: str | None = None,
        embedding_model: str | None = None,
        collection: str = DEFAULT_COLLECTION,
    ):
        self.persist_dir = persist_dir or os.environ.get("VECTOR_DIR", "./chroma_db")
        self.embedding_model = embedding_model or os.environ.get(
            "EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
        )
        self.collection_name = collection
        self._client = None
        self._collection = None
        self._embedder = None

    # --- lazy init helpers ---
    def _get_collection(self):
        if self._collection is None:
            import chromadb  # noqa: WPS433
            from chromadb.utils import embedding_functions  # noqa: WPS433

            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    # --- public API ---
    def add(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        col = self._get_collection()
        ids = [f"{c.source}::{c.chunk_id}" for c in chunks]
        docs = [c.text for c in chunks]
        metas = [
            {"source": c.source, "chunk_id": c.chunk_id, "language": c.language}
            for c in chunks
        ]
        col.upsert(ids=ids, documents=docs, metadatas=metas)

    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedPassage]:
        col = self._get_collection()
        # multilingual-e5 expects "query: ..." prefix for query-side
        prefixed = query if query.startswith(("query:", "passage:")) else f"query: {query}"
        result = col.query(query_texts=[prefixed], n_results=top_k)
        passages: list[RetrievedPassage] = []
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            passages.append(
                RetrievedPassage(
                    text=doc,
                    source=meta.get("source", ""),
                    chunk_id=int(meta.get("chunk_id", 0)),
                    language=meta.get("language", "en"),
                    score=1.0 - float(dist),
                )
            )
        return passages
