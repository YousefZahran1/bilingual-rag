"""API tests for the unified/unified_two_stage retrieval_mode wiring.

Retrieval is monkeypatched throughout -- these test the API contract (routing,
filter validation, the 409 not-built guard, citation shape) not the underlying
retrieval quality, which is eval/run_eval.py's job.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import app as app_module
from src.rag.store import RetrievedPassage

client = TestClient(app_module.app)


def _canned_unified_passages():
    return [
        RetrievedPassage(
            text="The co-payment is 30 SAR.",
            source="data/real/unified_contract.md",
            chunk_id=0,
            language="en",
            score=0.9,
            doc_type="contract",
            doc_title="Unified Contract",
            clause="20",
        )
    ]


def _canned_legacy_passages():
    return [
        RetrievedPassage(
            text="The co-payment is 30 SAR.",
            source="data/sample/01_health_plan_en.md",
            chunk_id=0,
            language="en",
            score=0.9,
        )
    ]


def test_unified_mode_happy_path(monkeypatch):
    monkeypatch.setattr(app_module, "_unified_ready", lambda: True)
    monkeypatch.setattr(app_module._unified, "retrieve", lambda *a, **k: _canned_unified_passages())

    r = client.post("/chat", json={"question": "What is the co-payment?", "retrieval_mode": "unified"})

    assert r.status_code == 200
    data = r.json()
    citation = data["citations"][0]
    assert citation["doc_type"] == "contract"
    assert citation["doc_title"] == "Unified Contract"
    assert citation["clause"] == "20"


def test_unified_two_stage_mode_routes_to_retrieve_two_stage(monkeypatch):
    monkeypatch.setattr(app_module, "_unified_ready", lambda: True)
    called = {}

    def fake_retrieve_two_stage(*a, **k):
        called["hit"] = True
        return _canned_unified_passages()

    monkeypatch.setattr(app_module._unified, "retrieve_two_stage", fake_retrieve_two_stage)

    r = client.post(
        "/chat", json={"question": "What is the co-payment?", "retrieval_mode": "unified_two_stage"}
    )

    assert r.status_code == 200
    assert called.get("hit") is True


def test_unified_mode_returns_409_when_index_not_built(monkeypatch):
    monkeypatch.setattr(app_module, "_unified_ready", lambda: False)

    r = client.post("/chat", json={"question": "What is the co-payment?", "retrieval_mode": "unified"})

    assert r.status_code == 409
    body = r.json()["detail"]
    assert body["error"] == "unified index not built"
    assert "python -m src.rag.pipeline build" in body["fix"]


def test_filters_reject_unknown_keys():
    r = client.post(
        "/chat",
        json={
            "question": "What is the co-payment?",
            "retrieval_mode": "unified",
            "filters": {"not_a_real_field": "x"},
        },
    )

    assert r.status_code == 422


def test_filters_accept_allowed_keys(monkeypatch):
    monkeypatch.setattr(app_module, "_unified_ready", lambda: True)
    seen = {}

    def fake_retrieve(query, filters=None, parent_k=4):
        seen["filters"] = filters
        return _canned_unified_passages()

    monkeypatch.setattr(app_module._unified, "retrieve", fake_retrieve)

    r = client.post(
        "/chat",
        json={
            "question": "What is the co-payment?",
            "retrieval_mode": "unified",
            "filters": {"doc_type": "formulary", "language": "ar"},
        },
    )

    assert r.status_code == 200
    assert seen["filters"] == {"doc_type": "formulary", "language": "ar"}


def test_legacy_dense_mode_citation_shape_unchanged(monkeypatch):
    monkeypatch.setattr(app_module._store, "retrieve", lambda *a, **k: _canned_legacy_passages())

    r = client.post("/chat", json={"question": "What is the co-payment?", "retrieval_mode": "dense"})

    assert r.status_code == 200
    citation = r.json()["citations"][0]
    assert set(citation) == {"index", "source", "chunk_id", "score", "doc_type", "doc_title", "clause"}
    assert citation["doc_type"] is None
    assert citation["doc_title"] is None
    assert citation["clause"] is None


def test_health_reports_unified_index_status(monkeypatch):
    monkeypatch.setattr(app_module, "_unified_ready", lambda: True)
    assert client.get("/health").json()["unified_index"] == "ready"

    monkeypatch.setattr(app_module, "_unified_ready", lambda: False)
    assert client.get("/health").json()["unified_index"] == "not_built"
