"""OpenRouter provider — only imported when LLM_PROVIDER=openrouter.

OpenRouter is a drop-in replacement for the OpenAI chat completions API
(same request/response shape, different base_url), so this reuses the
`openai` SDK rather than adding a new HTTP client dependency.

Default model is openai/gpt-oss-20b:free -- chosen empirically, not just by
spec sheet: tested three free, non-expiring OpenRouter models with a real
Arabic RAG-style question (data/sample/01_health_plan_en.md's daily room
cap), 2026-07-12. google/gemma-4-26b-a4b-it:free was consistently
rate-limited upstream (failed both attempts); nvidia/nemotron-nano-9b-v2:free
answered correctly but with a stray leading blank line and an English unit
mixed into the Arabic sentence; openai/gpt-oss-20b:free gave a clean, correct,
well-formatted Arabic answer on both tries. Override with OPENROUTER_MODEL if
OpenRouter's free lineup changes (check for "going away" flags on
openrouter.ai/models before picking a replacement).
"""
from __future__ import annotations

import os


class OpenRouterProvider:
    def __init__(self) -> None:
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            max_retries=5,
            timeout=60.0,
        )
        self._model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        # Free-tier OpenRouter models occasionally return a 200 with a
        # malformed/empty body (choices=None) instead of raising an HTTP
        # error -- seen in practice, not hypothetical. Surface a clear,
        # catchable error instead of a cryptic TypeError on `.choices[0]`.
        if not resp.choices:
            raise RuntimeError(
                f"OpenRouter returned no choices for model {self._model!r}: {resp!r}"
            )
        return resp.choices[0].message.content or ""
