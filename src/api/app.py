"""FastAPI service exposing /chat with citations."""
from __future__ import annotations

import os
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.rag.generator import generate
from src.rag.store import VectorStore

app = FastAPI(
    title="Bilingual RAG Assistant",
    version="0.1.0",
    summary="Arabic / English retrieval-augmented Q&A.",
)

# Reuse one store instance across requests
_store = VectorStore()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=20)


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
    return {"status": "ok", "version": "0.1.0"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    passages = _store.retrieve(req.question, top_k=req.top_k)
    result = generate(req.question, passages)
    return ChatResponse(
        answer=result.answer,
        citations=[Citation(**c) for c in result.citations],
        language=result.language,
    )
