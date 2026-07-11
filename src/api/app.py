"""FastAPI service exposing /chat with citations."""
from __future__ import annotations

from typing import List, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.rag.bm25_index import BM25Index
from src.rag.fusion import retrieve_pipeline
from src.rag.generator import generate
from src.rag.reranker import CrossEncoderReranker
from src.rag.store import VectorStore

app = FastAPI(
    title="Bilingual RAG Assistant",
    version="0.2.0",
    summary="Arabic / English retrieval-augmented Q&A.",
)

# Reuse one instance of each across requests
_store = VectorStore()
_bm25_index = BM25Index.load()
_reranker = CrossEncoderReranker()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)
    # Defaults to the new hybrid+rerank pipeline now that eval shows it's an
    # overall improvement; "dense" stays available for comparison/demo.
    retrieval_mode: Literal["dense", "hybrid_rerank"] = "hybrid_rerank"


class Citation(BaseModel):
    index: int
    source: str
    chunk_id: int
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    language: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if req.retrieval_mode == "hybrid_rerank":
        passages = retrieve_pipeline(
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
