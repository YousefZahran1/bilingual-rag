"""Tests for POST /chat/stream -- SSE event shape, citations-first ordering,
and that mid-stream provider failures close the stream with an error event
instead of hanging or crashing the server.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import app as app_module
from src.rag import generator as generator_module
from src.rag.store import RetrievedPassage

client = TestClient(app_module.app)


def _canned_passages():
    return [
        RetrievedPassage(
            text="The co-payment is 30 SAR.",
            source="data/sample/01_health_plan_en.md",
            chunk_id=0,
            language="en",
            score=0.9,
        )
    ]


def _parse_sse(body: str) -> list[tuple[str, str]]:
    events = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event, data))
    return events


def test_stream_emits_citations_first_then_tokens_then_done(monkeypatch):
    monkeypatch.setattr(app_module._store, "retrieve", lambda *a, **k: _canned_passages())

    with client.stream(
        "POST", "/chat/stream", json={"question": "What is the co-payment?", "retrieval_mode": "dense"}
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())

    events = _parse_sse(body)
    event_types = [e for e, _ in events]

    assert event_types[0] == "citations"
    assert event_types[-1] == "done"
    assert all(e in ("citations", "token", "done") for e in event_types)
    assert "token" in event_types  # MockProvider.stream() always yields something


def test_stream_citations_event_matches_chat_endpoint_shape(monkeypatch):
    monkeypatch.setattr(app_module._store, "retrieve", lambda *a, **k: _canned_passages())

    with client.stream(
        "POST", "/chat/stream", json={"question": "What is the co-payment?", "retrieval_mode": "dense"}
    ) as r:
        body = "".join(r.iter_text())

    import json

    events = _parse_sse(body)
    citations_data = json.loads(events[0][1])
    assert "citations" in citations_data
    assert "language" in citations_data
    citation = citations_data["citations"][0]
    assert citation["source"] == "data/sample/01_health_plan_en.md"


def test_stream_reassembled_tokens_match_mock_complete_answer(monkeypatch):
    monkeypatch.setattr(app_module._store, "retrieve", lambda *a, **k: _canned_passages())

    with client.stream(
        "POST", "/chat/stream", json={"question": "What is the co-payment?", "retrieval_mode": "dense"}
    ) as r:
        body = "".join(r.iter_text())

    import json

    events = _parse_sse(body)
    token_text = "".join(json.loads(data)["text"] for event, data in events if event == "token")

    non_stream = client.post("/chat", json={"question": "What is the co-payment?", "retrieval_mode": "dense"})
    assert token_text == non_stream.json()["answer"]


def test_stream_provider_error_emits_error_event_then_done(monkeypatch):
    monkeypatch.setattr(app_module._store, "retrieve", lambda *a, **k: _canned_passages())

    def _broken_stream(self, system, user):
        yield "partial "
        raise RuntimeError("upstream provider exploded")

    monkeypatch.setattr(generator_module.MockProvider, "stream", _broken_stream)

    with client.stream(
        "POST", "/chat/stream", json={"question": "What is the co-payment?", "retrieval_mode": "dense"}
    ) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())

    events = _parse_sse(body)
    event_types = [e for e, _ in events]
    assert "error" in event_types
    assert event_types[-1] == "done"


def test_stream_respects_409_unified_not_built(monkeypatch):
    monkeypatch.setattr(app_module, "_unified_ready", lambda: False)

    r = client.post(
        "/chat/stream", json={"question": "test", "retrieval_mode": "unified"}
    )
    assert r.status_code == 409
