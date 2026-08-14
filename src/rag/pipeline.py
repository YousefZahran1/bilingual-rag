"""Unified production retrieval pipeline (scaling plan steps 1-3).

Ties together the pieces proven out in docs/RETRIEVAL_TUNING.md:

  1. Per-document **strategy routing** — structured legal/regulatory docs
     (contract / policy / formulary / guideline) are chunked with the
     structure-aware splitter; anything else falls back to sentence/token
     chunking. Both go through parent-child so retrieval stays precise while
     generation gets full context.
  2. **Rich metadata** on every child (doc_id, doc_title, doc_type,
     clause_number, version, effective_date, language) for pre-search
     filtering — narrow the candidate set *before* the vector search.
  3. **Hybrid retrieval**: dense (multilingual-e5-small) + lexical (BM25) fused
     with Reciprocal Rank Fusion over the child chunks, top children expanded to
     their parent sections, which are what the LLM actually sees.

Persistence: a Chroma collection for the child vectors (HNSW cosine, payload
metadata filtering) plus two JSON sidecars — the parent map and the child
metadata map (also used to filter BM25 hits, which Chroma's `where` can't).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .bm25_index import BM25Index
from .chunker import Chunk
from .fusion import reciprocal_rank_fusion
from .lang import detect_language
from .parent_child import build_parents_children
from .store import RetrievedPassage

EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
FUSION_TOP_N = int(os.environ.get("RETRIEVAL_FUSION_TOP_N", "20"))
PARENT_K = int(os.environ.get("RETRIEVAL_PARENT_K", "4"))

# Document types that get structure-aware chunking; everything else uses token.
STRUCTURED_TYPES = {"contract", "policy", "formulary", "guideline"}
_TYPE_RULES = [
    ("contract", ("unified contract", "contract", "agreement")),
    ("formulary", ("formulary", "drug list", "(idf)")),
    ("guideline", ("guideline", "guidance", "clinical guideline")),
    ("policy", ("benefit package", "insurance policy", "essential benefit",
                "tiers benefit", "basic health insurance", "policy")),
]
_H1_RE = re.compile(r"^#\s+(.+)$", re.M)
_EFFECTIVE_RE = re.compile(r"effective[^\d]*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", re.I)
_DATE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{4}|20\d{2})")
_CLAUSE_RE = re.compile(r"(?m)^\s*(\d{1,3}(?:\.\d{1,3}){0,3})[.)]?\s+\S")
_LETTER_RE = re.compile(r"(?m)^\s*([A-Za-z])[.)]\s+\S")


def infer_doc_type(name: str, text: str) -> str:
    # Filename is the most reliable signal; fall back to a body scan.
    n = name.lower()
    if "faq" in n or "q&a" in n or "questions" in n:
        return "faq"
    if "contract" in n or "agreement" in n:
        return "contract"
    if "formulary" in n or "idf" in n:
        return "formulary"
    if "guideline" in n or "guidance" in n:
        return "guideline"
    if any(k in n for k in ("benefit", "policy", "tiers", "package", "coverage")):
        return "policy"
    hay = (name + " " + text[:800]).lower()
    for dtype, kws in _TYPE_RULES:
        if any(k in hay for k in kws):
            return dtype
    return "document"


def infer_effective_date(name: str, text: str) -> str:
    m = _EFFECTIVE_RE.search(name + " " + text[:800])
    if m:
        return m.group(1)
    m = _DATE_RE.search(name)
    return m.group(1) if m else ""


def extract_clause(text: str) -> str:
    m = _CLAUSE_RE.search(text)
    if m:
        return m.group(1)
    m = _LETTER_RE.search(text)
    return m.group(1) if m else ""


@dataclass
class DocMeta:
    doc_id: str
    doc_title: str
    doc_type: str
    version: str
    effective_date: str
    language: str
    strategy: str


def infer_doc_meta(path: Path) -> DocMeta:
    text = path.read_text(encoding="utf-8")
    dtype = infer_doc_type(path.name, text)
    title = (_H1_RE.search(text).group(1).strip() if _H1_RE.search(text) else path.stem)
    return DocMeta(
        doc_id=path.stem,
        doc_title=title,
        doc_type=dtype,
        version=os.environ.get("DOC_VERSION", "1.0"),
        effective_date=infer_effective_date(path.name, text),
        language=detect_language(text),
        strategy="structure" if dtype in STRUCTURED_TYPES else "token",
    )


def _build_where(filters: Optional[Dict[str, str]]):
    if not filters:
        return None
    conds = [{k: {"$eq": v}} for k, v in filters.items()]
    return conds[0] if len(conds) == 1 else {"$and": conds}


def _match(meta: Dict, filters: Optional[Dict[str, str]]) -> bool:
    return not filters or all(str(meta.get(k)) == str(v) for k, v in filters.items())


class UnifiedIndex:
    def __init__(self, persist_dir: str, collection: str = "unified_children"):
        self.persist_dir = persist_dir
        self.collection_name = collection
        self.parents_path = Path(persist_dir) / "parents.json"
        self.childmeta_path = Path(persist_dir) / "child_meta.json"
        self.bm25_path = str(Path(persist_dir) / "bm25_chunks.jsonl")
        self._col = None
        self._pcol = None
        self._embedder = None
        self._reranker = None
        self._parents: Dict[str, dict] = {}
        self._child_meta: Dict[str, dict] = {}
        self._bm25: Optional[BM25Index] = None

    def _collection(self):
        if self._col is None:
            import chromadb
            from chromadb.utils import embedding_functions

            os.makedirs(self.persist_dir, exist_ok=True)
            client = chromadb.PersistentClient(path=self.persist_dir)
            self._embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBED_MODEL
            )
            self._col = client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedder,
                metadata={"hnsw:space": "cosine"},
            )
            # Parent-summary collection for first-stage document/section routing.
            self._pcol = client.get_or_create_collection(
                name=f"{self.collection_name}_parents",
                embedding_function=self._embedder,
                metadata={"hnsw:space": "cosine"},
            )
        return self._col

    def _parent_collection(self):
        self._collection()
        return self._pcol

    def build(self, data_dir: str) -> dict:
        col = self._collection()
        parents: Dict[str, dict] = {}
        child_meta: Dict[str, dict] = {}
        bm25_chunks: List[Chunk] = []
        ids, docs, metas = [], [], []
        routing: Dict[str, str] = {}
        for f in sorted(Path(data_dir).glob("*.md")):
            if f.name in {"SOURCES.md", "README.md"}:
                continue
            dm = infer_doc_meta(f)
            routing[f.name] = f"{dm.doc_type}/{dm.strategy}"
            text = f.read_text(encoding="utf-8")
            source = f"{Path(data_dir).name}/{f.name}"
            ps, kids = build_parents_children(text, source, strategy=dm.strategy)
            for pid, ptext in ps.items():
                parents[pid] = {"text": ptext, "doc_id": dm.doc_id,
                                "doc_title": dm.doc_title, "doc_type": dm.doc_type,
                                "source": source}
            for c in kids:
                did = f"{c.source}::{c.chunk_id}"
                clause = extract_clause(c.text)
                meta = {
                    "source": c.source, "chunk_id": c.chunk_id, "parent_id": c.parent_id,
                    "doc_id": dm.doc_id, "doc_title": dm.doc_title, "doc_type": dm.doc_type,
                    "version": dm.version, "effective_date": dm.effective_date,
                    "language": c.language, "clause_number": clause,
                    "section_number": clause,  # alias per the metadata schema
                }
                ids.append(did)
                docs.append(c.text)
                metas.append(meta)
                # sidecar copy also carries the child text (for reranking) --
                # Chroma metadata deliberately does not, to avoid duplication.
                child_meta[did] = dict(meta, text=c.text)
                bm25_chunks.append(Chunk(c.text, c.source, c.chunk_id, c.language))
        embeddings = self._embedder([f"passage: {d}" for d in docs])
        col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        # First-stage parent-summary index.
        pids = list(parents.keys())
        if pids:
            p_docs = [parents[p]["text"] for p in pids]
            p_metas = [
                {"parent_id": p, "doc_id": parents[p]["doc_id"],
                 "doc_type": parents[p]["doc_type"], "source": parents[p]["source"]}
                for p in pids
            ]
            self._parent_collection().upsert(
                ids=pids, documents=p_docs, metadatas=p_metas,
                embeddings=self._embedder([f"passage: {d}" for d in p_docs]),
            )
        BM25Index(bm25_chunks).save(self.bm25_path)
        self.parents_path.write_text(json.dumps(parents, ensure_ascii=False), encoding="utf-8")
        self.childmeta_path.write_text(json.dumps(child_meta, ensure_ascii=False), encoding="utf-8")
        self._parents, self._child_meta = parents, child_meta
        return {"parents": len(parents), "children": len(docs), "routing": routing}

    def _load(self) -> None:
        if not self._parents:
            self._parents = json.loads(self.parents_path.read_text(encoding="utf-8"))
        if not self._child_meta:
            self._child_meta = json.loads(self.childmeta_path.read_text(encoding="utf-8"))
        if self._bm25 is None:
            self._bm25 = BM25Index.load(self.bm25_path)

    def _hybrid_children(self, query, where, filters, top_n):
        """Dense + BM25 + RRF over children. `where` is the Chroma filter for the
        dense side; `filters` metadata-filters the lexical side via child-meta."""
        col = self._collection()
        self._load()
        prefixed = query if query.startswith(("query:", "passage:")) else f"query: {query}"
        dense = col.query(query_texts=[prefixed], n_results=top_n, where=where)
        dense_ids = [f"{m['source']}::{m['chunk_id']}" for m in dense["metadatas"][0]]
        sparse_ids: List[str] = []
        for p in self._bm25.search(query, top_k=top_n * 3):
            did = f"{p.source}::{p.chunk_id}"
            if _match(self._child_meta.get(did, {}), filters):
                sparse_ids.append(did)
            if len(sparse_ids) >= top_n:
                break
        return reciprocal_rank_fusion([dense_ids, sparse_ids])

    def _expand_to_parents(self, fused, parent_k) -> List[RetrievedPassage]:
        parents: List[RetrievedPassage] = []
        seen: set = set()
        for did, score in fused:
            meta = self._child_meta.get(did)
            if not meta:
                continue
            pid = meta["parent_id"]
            if pid in seen:
                continue
            seen.add(pid)
            p = self._parents.get(pid, {})
            parents.append(
                RetrievedPassage(
                    text=p.get("text", ""),
                    source=p.get("source", meta["source"]),
                    chunk_id=len(parents),
                    language=meta.get("language", "en"),
                    score=round(float(score), 5),
                )
            )
            if len(parents) >= parent_k:
                break
        return parents

    def retrieve(
        self, query: str, filters: Optional[Dict[str, str]] = None, parent_k: int = PARENT_K
    ) -> List[RetrievedPassage]:
        """Single-stage: hybrid dense+BM25+RRF over children (optionally
        metadata-filtered), expanded to de-duplicated parent sections."""
        fused = self._hybrid_children(query, _build_where(filters), filters, FUSION_TOP_N)
        return self._expand_to_parents(fused, parent_k)

    def _get_reranker(self):
        if self._reranker is None:
            from .reranker import CrossEncoderReranker

            self._reranker = CrossEncoderReranker()
        return self._reranker

    def retrieve_two_stage(
        self,
        query: str,
        filters: Optional[Dict[str, str]] = None,
        first_k: int = 8,
        rerank_n: int = 24,
        parent_k: int = PARENT_K,
        use_reranker: bool = True,
    ) -> List[RetrievedPassage]:
        """Hierarchical retrieval: (1) route via the parent-summary index to a
        candidate set of documents, (2) hybrid child search restricted to them,
        (3) cross-encoder rerank the top children, (4) expand to parents."""
        self._load()
        pcol = self._parent_collection()
        prefixed = f"query: {query}"
        # Stage 1 -- document/section routing via parent summaries
        pres = pcol.query(
            query_texts=[prefixed], n_results=first_k, where=_build_where(filters)
        )
        cand_docs: List[str] = []
        for m in (pres.get("metadatas") or [[]])[0]:
            d = m.get("doc_id")
            if d and d not in cand_docs:
                cand_docs.append(d)
        # Stage 2 -- child hybrid restricted to candidate docs
        doc_where = {"doc_id": {"$in": cand_docs}} if cand_docs else None
        where = doc_where
        if filters:
            conds = [{k: {"$eq": v}} for k, v in filters.items()]
            if doc_where:
                conds.append(doc_where)
            where = {"$and": conds} if len(conds) > 1 else conds[0]
        fused = self._hybrid_children(query, where, filters, rerank_n)
        if cand_docs:
            restricted = [
                (did, s) for did, s in fused
                if self._child_meta.get(did, {}).get("doc_id") in cand_docs
            ]
            fused = restricted or fused
        # Stage 3 -- cross-encoder rerank the top children
        if use_reranker and fused:
            cand = [
                RetrievedPassage(
                    text=self._child_meta[did]["text"],
                    source=self._child_meta[did]["source"],
                    chunk_id=self._child_meta[did]["chunk_id"],
                    language=self._child_meta[did].get("language", "en"),
                    score=s,
                )
                for did, s in fused[:rerank_n]
                if did in self._child_meta
            ]
            reranked = self._get_reranker().rerank(query, cand, top_k=rerank_n)
            fused = [(f"{p.source}::{p.chunk_id}", p.rerank_score) for p in reranked]
        # Stage 4 -- expand to parents
        return self._expand_to_parents(fused, parent_k)
