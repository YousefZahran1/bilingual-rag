"""Parent-child ("small-to-big") retrieval.

Motivation (see docs/RETRIEVAL_TUNING.md for the paper trail): small chunks give
the best *retrieval* precision — a single clause isn't diluted into a page-sized
vector — but they can starve the LLM of context at *generation* time. Parent-
child retrieval decouples the two units:

  * CHILD chunks (small, structure-aware) are embedded and searched. Precise.
  * Each child records the PARENT (a larger clause-group) it belongs to.
  * At query time we retrieve children, then hand the LLM the de-duplicated
    PARENT text — precise matching, full-context generation.

Children are nested strictly inside parents (children are packed *within* each
parent's segment run), so a child always maps to exactly one parent.

This module reuses the structure segmentation from `chunker.py` and the same
`intfloat/multilingual-e5-small` embeddings + "passage:"/"query:" prefixes as
`store.py`, so retrieval behaviour is comparable to the main pipeline.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .chunker import SENTENCE_SPLIT, _segments, _split_oversized, _token_len
from .lang import detect_language


def _atoms(text: str, strategy: str) -> list[str]:
    """Smallest indivisible units to pack into parents/children.

    - "structure": clause/section segments (numbered legal text).
    - "token": sentences (unstructured prose / FAQs), so token-strategy docs
      still get fine-grained children for precise matching.
    """
    if strategy == "structure":
        return _segments(text)
    atoms: list[str] = []
    for para in text.split("\n\n"):
        for sent in SENTENCE_SPLIT.split(para.strip()):
            s = sent.strip()
            if s:
                atoms.append(s)
    return atoms

CHILD_MAX = int(os.environ.get("CHILD_MAX_TOKENS", "200"))
PARENT_MAX = int(os.environ.get("PARENT_MAX_TOKENS", "900"))
DEFAULT_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")


@dataclass
class ParentPassage:
    parent_id: str
    text: str
    source: str
    score: float  # best child score that mapped to this parent


@dataclass
class _Child:
    text: str
    source: str
    chunk_id: int
    parent_id: str
    language: str


def _pack_groups(segments: list[str], budget: int) -> list[list[str]]:
    """Greedily pack an ordered list of structural segments into contiguous
    groups, each <= budget tokens (an oversized single segment stands alone)."""
    groups: list[list[str]] = []
    cur: list[str] = []
    tok = 0
    for seg in segments:
        st = _token_len(seg)
        if st > budget:
            if cur:
                groups.append(cur)
                cur, tok = [], 0
            groups.append([seg])
            continue
        if cur and tok + st > budget:
            groups.append(cur)
            cur, tok = [], 0
        cur.append(seg)
        tok += st
    if cur:
        groups.append(cur)
    return groups


def build_parents_children(
    text: str, source: str, strategy: str = "structure"
) -> tuple[dict[str, str], list[_Child]]:
    """Return ({parent_id: parent_text}, [children]) for one document."""
    segs = _atoms(text, strategy)
    parents: dict[str, str] = {}
    children: list[_Child] = []
    cid = 0
    for pid, parent_group in enumerate(_pack_groups(segs, PARENT_MAX)):
        parent_id = f"{source}::P{pid}"
        parents[parent_id] = "\n".join(parent_group).strip()
        # pack children strictly within this parent's segment run
        for child_group in _pack_groups(parent_group, CHILD_MAX):
            ctext = "\n".join(child_group).strip()
            for piece in _split_oversized(ctext):
                children.append(
                    _Child(piece, source, cid, parent_id, detect_language(piece))
                )
                cid += 1
    return parents, children


class ParentChildIndex:
    """Chroma-backed child index + an on-disk parent map."""

    def __init__(self, persist_dir: str, collection: str = "pc_children"):
        self.persist_dir = persist_dir
        self.collection_name = collection
        self.parent_path = Path(persist_dir) / "parents.json"
        self._col = None
        self._embedder = None
        self._parents: dict[str, str] = {}

    def _collection(self):
        if self._col is None:
            import chromadb
            from chromadb.utils import embedding_functions

            os.makedirs(self.persist_dir, exist_ok=True)
            client = chromadb.PersistentClient(path=self.persist_dir)
            self._embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=DEFAULT_MODEL
            )
            self._col = client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedder,
                metadata={"hnsw:space": "cosine"},
            )
        return self._col

    def build_from_dir(self, data_dir: str) -> tuple[int, int]:
        col = self._collection()
        parents: dict[str, str] = {}
        docs, ids, metas = [], [], []
        for f in sorted(Path(data_dir).glob("*.md")):
            if f.name in {"SOURCES.md", "README.md"}:
                continue
            p, kids = build_parents_children(
                f.read_text(encoding="utf-8"), f"{Path(data_dir).name}/{f.name}"
            )
            parents.update(p)
            for c in kids:
                ids.append(f"{c.source}::{c.chunk_id}")
                docs.append(c.text)
                metas.append(
                    {"source": c.source, "chunk_id": c.chunk_id, "parent_id": c.parent_id}
                )
        embeddings = self._embedder([f"passage: {d}" for d in docs])
        col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        self._parents = parents
        self.parent_path.write_text(json.dumps(parents, ensure_ascii=False), encoding="utf-8")
        return len(parents), len(docs)

    def _load_parents(self) -> dict[str, str]:
        if not self._parents:
            self._parents = json.loads(self.parent_path.read_text(encoding="utf-8"))
        return self._parents

    def retrieve_parents(self, query: str, child_k: int = 8, parent_k: int = 4) -> list[ParentPassage]:
        """Retrieve top child chunks, then return the de-duplicated parents they
        belong to (order preserved by best child score)."""
        col = self._collection()
        parents = self._load_parents()
        prefixed = query if query.startswith(("query:", "passage:")) else f"query: {query}"
        res = col.query(query_texts=[prefixed], n_results=child_k)
        seen: dict[str, ParentPassage] = {}
        for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
            pid = meta.get("parent_id", "")
            score = 1.0 - float(dist)
            if pid not in seen:
                seen[pid] = ParentPassage(
                    parent_id=pid,
                    text=parents.get(pid, ""),
                    source=meta.get("source", ""),
                    score=score,
                )
            if len(seen) >= parent_k:
                break
        return list(seen.values())
