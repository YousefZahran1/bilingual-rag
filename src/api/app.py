"""FastAPI service exposing /chat with citations."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.rag.bm25_index import BM25Index
from src.rag.fusion import retrieve_pipeline, smart_retrieve
from src.rag.generator import generate
from src.rag.pipeline import UnifiedIndex
from src.rag.reranker import CrossEncoderReranker
from src.rag.store import VectorStore

load_dotenv()

app = FastAPI(
    title="Bilingual RAG Assistant",
    version="0.4.0",
    summary="Arabic / English retrieval-augmented Q&A.",
)

# Reuse one instance of each across requests
_store = VectorStore()
_bm25_index = BM25Index.load()
_reranker = CrossEncoderReranker()

UNIFIED_INDEX_DIR = os.environ.get("UNIFIED_INDEX_DIR", "./unified_index")
# Constructing UnifiedIndex doesn't touch disk (see pipeline.py __init__) --
# safe to build eagerly even if the index hasn't been built yet. Only
# .retrieve()/.retrieve_two_stage() (via _load()) touch the sidecar files,
# and that failure is handled per-request below (409, not a startup crash).
_unified = UnifiedIndex(UNIFIED_INDEX_DIR)

# What a request may filter on -- an allowlist, not a passthrough of
# arbitrary user-supplied keys into Chroma's `where` clause.
ALLOWED_FILTER_KEYS = {"doc_type", "language", "doc_id", "version"}


def _unified_ready() -> bool:
    return Path(_unified.parents_path).exists() and Path(_unified.childmeta_path).exists()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)
    # Defaults to "hybrid_rerank" as of v0.7 (was "smart"). "smart" was
    # designed and tuned against an 89-question eval set where the
    # cross-encoder reranker measurably hurt numeric questions and BM25
    # alone was the best numeric performer -- that premise no longer holds
    # on the current 118-question set (dev and test split both re-checked):
    # hybrid_rerank now matches or beats every individual mode, including
    # smart, on recall@1, recall@4, and keyword_coverage. BM25-alone is no
    # longer the best choice even within the numeric subset specifically --
    # this isn't a router-classification bug (precision/recall against the
    # "numeric" tag are still ~0.89/0.88), the underlying retrieval
    # landscape changed. See docs/EVAL.md's "v0.7: smart-router re-tune"
    # section for the full per-subset, dev/test-split investigation.
    # "smart" stays selectable for comparison -- it still ties hybrid_rerank
    # on data/real2, so the routing idea isn't dead, just not universally
    # best. "unified"/"unified_two_stage" use UnifiedIndex (metadata
    # filters, parent-child expansion) -- see docs/PIPELINE.md.
    retrieval_mode: Literal[
        "dense", "hybrid_rerank", "smart", "unified", "unified_two_stage"
    ] = "hybrid_rerank"
    filters: dict[str, str] | None = Field(
        default=None,
        description=f"Metadata pre-filter for unified/unified_two_stage modes. "
        f"Allowed keys: {sorted(ALLOWED_FILTER_KEYS)}. Ignored by other modes.",
    )

    @field_validator("filters")
    @classmethod
    def _validate_filter_keys(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        unknown = set(v) - ALLOWED_FILTER_KEYS
        if unknown:
            raise ValueError(
                f"Unknown filter key(s) {sorted(unknown)}; allowed: {sorted(ALLOWED_FILTER_KEYS)}"
            )
        return v


class Citation(BaseModel):
    index: int
    source: str
    chunk_id: int
    score: float
    # Populated only for unified/unified_two_stage retrieval; null for
    # legacy modes -- additive fields, so old clients that ignore unknown
    # JSON keys see the same effective shape.
    doc_type: str | None = None
    doc_title: str | None = None
    clause: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    language: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "0.4.0",
        "unified_index": "ready" if _unified_ready() else "not_built",
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if req.retrieval_mode in ("unified", "unified_two_stage"):
        if not _unified_ready():
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "unified index not built",
                    "fix": f"python -m src.rag.pipeline build data/real --persist {UNIFIED_INDEX_DIR}",
                },
            )
        if req.retrieval_mode == "unified":
            passages = _unified.retrieve(req.question, filters=req.filters, parent_k=req.top_k)
        else:
            passages = _unified.retrieve_two_stage(
                req.question, filters=req.filters, parent_k=req.top_k
            )
    elif req.retrieval_mode == "hybrid_rerank":
        passages = retrieve_pipeline(
            req.question, _store, _bm25_index, _reranker, top_k=req.top_k
        )
    elif req.retrieval_mode == "smart":
        passages = smart_retrieve(
            req.question, _store, _bm25_index, _reranker, top_k=req.top_k
        )
    else:
        passages = _store.retrieve(req.question, top_k=req.top_k)
    result = generate(req.question, passages)
    return ChatResponse(
        answer=result.answer,
        citations=[Citation(**c) for c in result.citations],
        language=result.language,
    )
