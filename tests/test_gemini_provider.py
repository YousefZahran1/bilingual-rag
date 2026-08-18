"""GeminiProvider tests -- the OpenAI client is fully mocked; this never
makes a real network call, matching every other test in this repo.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.rag.providers.gemini_provider import MAX_TOKENS, GeminiProvider


class _FakeCompletions:
    def __init__(self, response=None, chunks=None):
        self._response = response
        self._chunks = chunks or []
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        if kwargs.get("stream"):
            return iter(self._chunks)
        return self._response


class _FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def _make_provider(monkeypatch, completions):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr("openai.OpenAI", lambda **kw: _FakeClient(completions))
    return GeminiProvider()


def _completion_response(text: str):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _stream_chunk(text: str | None):
    delta = SimpleNamespace(content=text)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice])


def test_complete_returns_message_content(monkeypatch):
    completions = _FakeCompletions(response=_completion_response("30 SAR"))
    provider = _make_provider(monkeypatch, completions)

    result = provider.complete("system prompt", "What is the co-payment?")

    assert result == "30 SAR"


def test_complete_caps_max_tokens(monkeypatch):
    completions = _FakeCompletions(response=_completion_response("answer"))
    provider = _make_provider(monkeypatch, completions)

    provider.complete("system", "user")

    assert completions.last_call_kwargs["max_tokens"] == MAX_TOKENS


def test_complete_raises_on_empty_choices(monkeypatch):
    completions = _FakeCompletions(response=SimpleNamespace(choices=[]))
    provider = _make_provider(monkeypatch, completions)

    with pytest.raises(RuntimeError, match="no choices"):
        provider.complete("system", "user")


def test_stream_yields_deltas_and_skips_empty_chunks(monkeypatch):
    chunks = [_stream_chunk("Hel"), _stream_chunk(None), _stream_chunk("lo")]
    completions = _FakeCompletions(chunks=chunks)
    provider = _make_provider(monkeypatch, completions)

    result = list(provider.stream("system", "user"))

    assert result == ["Hel", "lo"]


def test_stream_caps_max_tokens(monkeypatch):
    completions = _FakeCompletions(chunks=[_stream_chunk("x")])
    provider = _make_provider(monkeypatch, completions)

    list(provider.stream("system", "user"))

    assert completions.last_call_kwargs["max_tokens"] == MAX_TOKENS


def test_uses_gemini_model_env_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-flash")
    completions = _FakeCompletions(response=_completion_response("x"))
    provider = _make_provider(monkeypatch, completions)

    provider.complete("system", "user")

    assert completions.last_call_kwargs["model"] == "gemini-1.5-flash"


def test_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(KeyError):
        GeminiProvider()
