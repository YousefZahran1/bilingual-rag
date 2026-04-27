"""Answer generation with pluggable LLM provider.

Default `mock` provider returns a templated extractive answer so the pipeline
runs end-to-end without an API key. Swap to `openai` or `anthropic` via env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Protocol

from .lang import detect_language
from .store import RetrievedPassage


@dataclass
class AnswerWithCitations:
    answer: str
    citations: List[dict]
    language: str


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class MockProvider:
    """Deterministic extractive 'answer' for testing without API keys."""

    def complete(self, system: str, user: str) -> str:
        # Take the first 280 chars of the retrieved-passages block as the "answer"
        idx = user.find("Passages:")
        if idx == -1:
            return "I do not know based on the retrieved passages."
        body = user[idx + len("Passages:") :].strip()
        return body[:300] + ("..." if len(body) > 300 else "")


def _build_prompt(query: str, passages: List[RetrievedPassage], lang: str) -> tuple[str, str]:
    if lang == "ar":
        sys = (
            "أنت مساعد يجيب على الأسئلة استنادًا إلى المقاطع التالية فقط. "
            "إذا لم يكن الجواب موجودًا في المقاطع، قل لا أعلم. "
            "اذكر المصدر بين قوسين بعد كل جملة تستخدم فيها المعلومة."
        )
    else:
        sys = (
            "You answer questions strictly from the supplied passages. "
            "If the answer is not in the passages, say you don't know. "
            "Cite the source in parentheses after every sentence that uses retrieved information."
        )
    passage_block = "\n\n".join(
        f"[{i+1}] (source: {p.source}, chunk_id: {p.chunk_id})\n{p.text}"
        for i, p in enumerate(passages)
    )
    user = f"Question: {query}\n\nPassages:\n{passage_block}"
    return sys, user


def _provider() -> LLMProvider:
    name = os.environ.get("LLM_PROVIDER", "mock").lower()
    if name == "mock":
        return MockProvider()
    if name == "openai":
        from .providers.openai_provider import OpenAIProvider  # type: ignore

        return OpenAIProvider()
    if name == "anthropic":
        from .providers.anthropic_provider import AnthropicProvider  # type: ignore

        return AnthropicProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")


def generate(query: str, passages: List[RetrievedPassage]) -> AnswerWithCitations:
    lang = detect_language(query)
    sys, user = _build_prompt(query, passages, lang)
    provider = _provider()
    answer = provider.complete(sys, user).strip()
    citations = [
        {"index": i + 1, "source": p.source, "chunk_id": p.chunk_id, "score": round(p.score, 3)}
        for i, p in enumerate(passages)
    ]
    return AnswerWithCitations(answer=answer, citations=citations, language=lang)
