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


def _register(email: str, password: str, **extra):
    # All tests share one TestClient/IP -- clear the per-IP register
    # throttle first so an earlier test's attempts don't backoff-block
    # this one.
    routes_module._REGISTER_ATTEMPTS_BY_IP.clear()
    return client.post("/auth/register", json={"email": email, "password": password, **extra})


def _login(email: str, password: str) -> dict:
    routes_module._FAILURES_BY_IP.clear()
    return client.post("/auth/login", json={"email": email, "password": password})


# --- registration -----------------------------------------------------


def test_register_creates_user():
    r = _register(_unique_email("reg"), "password123")
    assert r.status_code == 201


def test_register_duplicate_email_rejected_generically():
    email = _unique_email("dup")
    _register(email, "password123")
    r = _register(email, "password123")
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_register_duplicate_email_case_insensitive():
    base = f"casedup-{uuid.uuid4().hex}"
    r1 = _register(f"{base}@example.com", "password123")
    assert r1.status_code == 201
    r2 = _register(f"{base.upper()}@EXAMPLE.COM", "password123")
    assert r2.status_code == 400


def test_register_weak_password_rejected():
    r = _register(_unique_email("weak"), "short")
    assert r.status_code == 422


def test_register_honeypot_silently_creates_nothing():
    email = _unique_email("bot")
    r = _register(email, "password123", website="http://spam.example")
    assert r.status_code == 201  # same response a real registration gets
    r2 = _login(email, "password123")
    assert r2.status_code == 401  # no account was actually created


def test_register_second_attempt_from_same_ip_is_backoff_limited():
    routes_module._REGISTER_ATTEMPTS_BY_IP.clear()
    r1 = client.post(
        "/auth/register", json={"email": _unique_email("regback1"), "password": "password123"}
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/auth/register", json={"email": _unique_email("regback2"), "password": "password123"}
    )
    assert r2.status_code == 429


# --- login + rate limiting ---------------------------------------------


def test_login_success_returns_token():
    email = _unique_email("login")
    _register(email, "password123")
    r = _login(email, "password123")
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_case_insensitive_email():
    email = _unique_email("logincase")
    _register(email, "password123")
    r = _login(email.upper(), "password123")
    assert r.status_code == 200


def test_login_wrong_password_rejected_generically():
    email = _unique_email("wrongpw")
    _register(email, "password123")
    r = _login(email, "nope12345")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid email or password"


def test_login_nonexistent_email_returns_generic_401():
    r = _login(_unique_email("nope"), "whatever123")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid email or password"


def test_login_ip_backoff_blocks_immediate_retry_after_failure():
    email = _unique_email("backoff")
    _register(email, "password123")
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
    _register(email, "correctpassword")
    for _ in range(routes_module.RATE_LIMIT_MAX_ATTEMPTS):
        r = _login(email, "wrong")
        assert r.status_code == 401
    r = _login(email, "correctpassword")
    assert r.status_code == 429


def test_lockout_is_bounded_and_not_renewed_by_continued_attempts(monkeypatch):
    """A victim locked out by an attacker must recover on its own -- the
    lockout window is fixed at the moment it's triggered, not extended by
    every subsequent failed attempt (which would let an attacker sending
    one request every <15 minutes keep the account locked forever)."""
    email = _unique_email("boundedlockout")
    _register(email, "correctpassword")

    fake_now = [1_000_000.0]
    monkeypatch.setattr(routes_module.time, "time", lambda: fake_now[0])

    for _ in range(routes_module.RATE_LIMIT_MAX_ATTEMPTS):
        routes_module._FAILURES_BY_IP.clear()
        r = client.post("/auth/login", json={"email": email, "password": "wrong"})
        assert r.status_code == 401
        fake_now[0] += 1

    routes_module._FAILURES_BY_IP.clear()
    r = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 429  # locked out

    fake_now[0] += routes_module.RATE_LIMIT_WINDOW_S + 1
    routes_module._FAILURES_BY_IP.clear()
    r = client.post("/auth/login", json={"email": email, "password": "correctpassword"})
    assert r.status_code == 200  # lockout expired on its own


def test_prune_deletes_empty_bucket_key():
    """Regression guard for unbounded pre-auth memory growth: a bucket
    whose entries have all expired must not leave a permanent, empty dict
    entry behind for every distinct email/IP an attacker ever probed."""
    store: dict[str, list[float]] = {}
    now = 1000.0
    routes_module._record(store, "probe@example.com", now)
    assert "probe@example.com" in store

    later = now + routes_module.RATE_LIMIT_WINDOW_S + 1
    result = routes_module._prune(store, "probe@example.com", later)
    assert result == []
    assert "probe@example.com" not in store


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


def _auth_headers(email: str, password: str) -> dict[str, str]:
    r = _login(email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mock_provider_does_not_count_against_quota(monkeypatch):
    email = _unique_email("mockquota")
    _register(email, "password123")
    headers = _auth_headers(email, "password123")

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    r = client.post("/chat", json={"question": "what is the co-payment?"}, headers=headers)
    assert r.status_code == 200

    r = client.get("/auth/me", headers=headers)
    assert r.json()["queries_used"] == 0


def test_quota_exhausted_returns_429_with_shape(monkeypatch):
    email = _unique_email("exhausted")
    _register(email, "password123")
    headers = _auth_headers(email, "password123")

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
