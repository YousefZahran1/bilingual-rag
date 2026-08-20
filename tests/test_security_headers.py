"""Every response carries the app-code-owned security headers -- HTTPS
itself is a deploy-layer concern (see docs/SECURITY.md), not tested here.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import app as app_module

client = TestClient(app_module.app)


def test_health_response_has_security_headers():
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]


def test_404_response_still_has_security_headers():
    r = client.get("/no-such-route")
    assert r.status_code == 404
    assert r.headers["x-content-type-options"] == "nosniff"
