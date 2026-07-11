"""BM25 sparse retriever, persisted as a JSONL sidecar of chunk records.

Kept separate from Chroma's own persistence directory (a different env var,
INDEX_DIR) so nothing not owned by Chroma lives inside chroma_db/. Persisting
as a JSONL of chunks -- rather than binary-serializing the fitted BM25Okapi
object -- keeps the sidecar human-diffable, safe to commit to git, and stable
across rank_bm25/Python version upgrades; rebuilding the term-frequency index
from tokenized text at load time is pure Python and fast.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from rank_bm25 import BM25Okapi

from .chunker import Chunk
from .lang import tokenize
from .store import RetrievedPassage

DEFAULT_INDEX_DIR = "./index_data"
SIDECAR_FILENAME = "bm25_chunks.jsonl"


class BM25Index:
    def __init__(self, chunks: Optional[List[Chunk]] = None):
        self._chunks: List[Chunk] = list(chunks) if chunks else []
        self._bm25: Optional[BM25Okapi] = None
        if self._chunks:
            self._rebuild()

    def _rebuild(self) -> None:
        tokenized = [tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized)

    @classmethod
    def build(cls, chunks: List[Chunk]) -> "BM25Index":
        return cls(chunks)

    def add(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        self._chunks.extend(chunks)
        self._rebuild()

    def search(self, query: str, top_k: int = 4) -> List[RetrievedPassage]:
        if not self._chunks or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            RetrievedPassage(
                text=self._chunks[i].text,
                source=self._chunks[i].source,
                chunk_id=self._chunks[i].chunk_id,
                language=self._chunks[i].language,
                score=float(scores[i]),
            )
            for i in ranked_idx
        ]

    def save(self, path: Optional[str] = None) -> None:
        target = Path(path) if path else self._default_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            for c in self._chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Optional[str] = None) -> "BM25Index":
        source = Path(path) if path else cls._default_path()
        if not source.exists():
            return cls([])
        chunks = []
        with source.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                chunks.append(
                    Chunk(
                        text=d["text"],
                        source=d["source"],
                        chunk_id=d["chunk_id"],
                        language=d["language"],
                    )
                )
        return cls(chunks)

    @staticmethod
    def _default_path() -> Path:
        index_dir = os.environ.get("INDEX_DIR", DEFAULT_INDEX_DIR)
        return Path(index_dir) / SIDECAR_FILENAME
