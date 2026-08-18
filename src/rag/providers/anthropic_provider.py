"""Anthropic provider — only imported when LLM_PROVIDER=anthropic."""
from __future__ import annotations

import os
from collections.abc import Iterator


class AnthropicProvider:
    def __init__(self) -> None:
        from anthropic import Anthropic  # type: ignore

        self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    def complete(self, system: str, user: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.1,
        )
        return "".join(block.text for block in msg.content if block.type == "text")

    def stream(self, system: str, user: str) -> Iterator[str]:
        # Anthropic's streaming shape differs from the OpenAI-compatible
        # providers -- a context manager exposing .text_stream, not an
        # iterable of chunks with a .choices[0].delta path.
        with self._client.messages.stream(
            model=self._model,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.1,
        ) as stream:
            yield from stream.text_stream
