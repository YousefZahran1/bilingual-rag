"""OpenAI provider — only imported when LLM_PROVIDER=openai."""
from __future__ import annotations

import os


class OpenAIProvider:
    def __init__(self) -> None:
        from openai import OpenAI  # type: ignore

        self._client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""
