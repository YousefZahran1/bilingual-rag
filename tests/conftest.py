"""Shared test fixtures.

Auth defaults to a fake authenticated user via FastAPI's
dependency_overrides so retrieval/streaming tests (written before
accounts existed) don't need to register/login -- they aren't testing
auth, and forcing every one of them to carry real credentials would just
be noise. tests/test_auth.py clears this override for the tests that
exercise the real auth flow.
"""
from __future__ import annotations

import os

os.environ.setdefault("AUTH_DB_PATH", ":memory:")
os.environ.setdefault("LLM_PROVIDER", "mock")

import pytest

from src.api.app import app
from src.auth.models import User
from src.auth.routes import get_current_user

TEST_USER = User(
    id=1, email="fixture@example.com", password_hash="x", queries_used=0, query_limit=10_000
)


@pytest.fixture(autouse=True)
def _fake_auth():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)
