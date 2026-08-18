"""Auth: registration, login + rate limiting, JWT, and quota enforcement.

Unlike the other API test files, these tests exercise the real
get_current_user dependency -- conftest.py's autouse fake-auth override
(meant for tests that aren't about auth) is cleared for this whole module.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from sqlalchemy.orm import sessionmaker

from src.api.app import app
from src.auth import routes as routes_module
from src.auth.models import User, get_session, make_engine
from src.auth.quota import try_consume_query
from src.auth.routes import get_current_user
from src.auth.security import (
    JWT_ALGORITHM,
    _get_jwt_secret,
    create_access_token,
    decode_access_token,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _use_real_auth():
    app.dependency_overrides.pop(get_current_user, None)
    yield


def _unique_email(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex}@example.com"


# --- registration -----------------------------------------------------


def test_register_creates_user():
    r = client.post("/auth/register", json={"email": _unique_email("reg"), "password": "password123"})
    assert r.status_code == 201


def test_register_duplicate_email_rejected_generically():
    email = _unique_email("dup")
    client.post("/auth/register", json={"email": email, "password": "password123"})
    r = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_register_weak_password_rejected():
    r = client.post("/auth/register", json={"email": _unique_email("weak"), "password": "short"})
    assert r.status_code == 422


def test_register_honeypot_silently_creates_nothing():
    email = _unique_email("bot")
    r = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "website": "http://spam.example"},
    )
    assert r.status_code == 201  # same response a real registration gets
    routes_module._FAILURES_BY_IP.clear()
    r2 = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r2.status_code == 401  # no account was actually created


# --- login + rate limiting ---------------------------------------------


def test_login_success_returns_token():
    email = _unique_email("login")
    client.post("/auth/register", json={"email": email, "password": "password123"})
    routes_module._FAILURES_BY_IP.clear()
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password_rejected_generically():
    email = _unique_email("wrongpw")
    client.post("/auth/register", json={"email": email, "password": "password123"})
    routes_module._FAILURES_BY_IP.clear()
    r = client.post("/auth/login", json={"email": email, "password": "nope12345"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid email or password"


def test_login_ip_backoff_blocks_immediate_retry_after_failure():
    email = _unique_email("backoff")
    client.post("/auth/register", json={"email": email, "password": "password123"})
    routes_module._FAILURES_BY_EMAIL.clear()
    routes_module._FAILURES_BY_IP.clear()
    r1 = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert r1.status_code == 401
    r2 = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r2.status_code == 429


def test_login_rate_limited_after_max_attempts():
    # Clears the IP bucket between attempts to isolate the per-email
    # fixed-window limit from the separate IP-backoff mechanism (covered
    # by test_login_ip_backoff_blocks_immediate_retry_after_failure).
    email = _unique_email("ratelimit")
    client.post("/auth/register", json={"email": email, "password": "correctpassword"})
    for _ in range(routes_module.RATE_LIMIT_MAX_ATTEMPTS):
        routes_module._FAILURES_BY_IP.clear()
        r = client.post("/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401
    routes_module._FAILURES_BY_IP.clear()
    r = client.post("/auth/login", json={"email": email, "password": "correctpassword"})
    assert r.status_code == 429


# --- JWT -----------------------------------------------------------------


def test_jwt_roundtrip_valid():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


def test_jwt_expired_token_rejected():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
        _get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(JWTError):
        decode_access_token(expired)


def test_jwt_tampered_token_rejected():
    token = create_access_token(1)
    last_char = token[-1]
    tampered = token[:-1] + ("0" if last_char != "0" else "1")
    with pytest.raises(JWTError):
        decode_access_token(tampered)


def test_get_current_user_rejects_missing_header():
    r = client.post("/chat", json={"question": "test"})
    assert r.status_code == 401


def test_get_current_user_rejects_malformed_header():
    r = client.post("/chat", json={"question": "test"}, headers={"Authorization": "garbage"})
    assert r.status_code == 401


# --- quota enforcement -----------------------------------------------------


def _login(email: str, password: str) -> dict[str, str]:
    routes_module._FAILURES_BY_IP.clear()
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mock_provider_does_not_count_against_quota(monkeypatch):
    email = _unique_email("mockquota")
    client.post("/auth/register", json={"email": email, "password": "password123"})
    headers = _login(email, "password123")

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    r = client.post("/chat", json={"question": "what is the co-payment?"}, headers=headers)
    assert r.status_code == 200

    r = client.get("/auth/me", headers=headers)
    assert r.json()["queries_used"] == 0


def test_quota_exhausted_returns_429_with_shape(monkeypatch):
    email = _unique_email("exhausted")
    client.post("/auth/register", json={"email": email, "password": "password123"})
    headers = _login(email, "password123")

    db_gen = get_session()
    db = next(db_gen)
    user = db.query(User).filter(User.email == email).first()
    user.query_limit = 0
    db.commit()

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    r = client.post("/chat", json={"question": "test"}, headers=headers)
    assert r.status_code == 429
    assert r.json()["detail"] == {"error": "query limit reached", "limit": 0, "used": 0}


def test_quota_concurrent_requests_only_one_succeeds(tmp_path):
    """N threads race to consume the last remaining query on one account,
    each against its own Session but the same file-backed SQLite DB (real
    multi-connection concurrency, exercising the busy_timeout PRAGMA) --
    the atomic UPDATE...WHERE in quota.py must let exactly one through."""
    db_path = str(tmp_path / "quota_race.db")
    engine = make_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        user = User(email="race@example.com", password_hash="x", query_limit=1)
        db.add(user)
        db.commit()
        user_id = user.id

    results: list[bool] = []
    lock = threading.Lock()

    def _attempt() -> None:
        with SessionLocal() as db:
            allowed = try_consume_query(db, user_id)
        with lock:
            results.append(allowed)

    threads = [threading.Thread(target=_attempt) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 1
    assert results.count(False) == 9
