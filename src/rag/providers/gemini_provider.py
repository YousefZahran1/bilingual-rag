"""Gemini provider — only imported when LLM_PROVIDER=gemini.

Gemini exposes an OpenAI-compatible chat completions endpoint, so this
reuses the `openai` SDK rather than adding the separate `google-genai`
dependency -- same pattern as openrouter_provider.py, just a different
base_url. max_tokens is capped explicitly: Gemini's flash-tier models have
no default cap the way some providers do, and this app never needs more
than a short grounded answer.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

MAX_TOKENS = 800


class GeminiProvider:
    def __init__(self) -> None:
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=os.environ["GEMINI_API_KEY"],
            max_retries=5,
            timeout=60.0,
        )
        self._model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=MAX_TOKENS,
        )
        if not resp.choices:
            raise RuntimeError(f"Gemini returned no choices for model {self._model!r}: {resp!r}")
        return resp.choices[0].message.content or ""

    def stream(self, system: str, user: str) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
