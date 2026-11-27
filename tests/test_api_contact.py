"""Интеграционные тесты API /api/contact."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

VALID = {
    "name": "Иван Петров",
    "email": "ivan@example.com",
    "phone": "+7 999 123-45-67",
    "comment": "Здравствуйте! Хочу обсудить проект.",
}


def test_contact_success_has_rate_limit_headers(client):
    r = client.post("/api/contact", json=VALID)
    assert r.status_code == 201
    assert "X-RateLimit-Limit" in r.headers
    assert "X-RateLimit-Remaining" in r.headers
    body = r.json()
    assert body["email_queued"] is True
    assert body["analysis"]["sentiment"]


def test_contact_validation_422(client):
    r = client.post("/api/contact", json={**VALID, "email": "bad"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_contact_rate_limit_429(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "2")
    from app.core import config
    config.get_settings.cache_clear()
    c = TestClient(app)
    c.post("/api/contact", json=VALID)
    c.post("/api/contact", json=VALID)
    r = c.post("/api/contact", json=VALID)
    assert r.status_code == 429
    assert r.headers.get("Retry-After")
    assert r.headers.get("X-RateLimit-Remaining") == "0"
    config.get_settings.cache_clear()


def test_honeypot_silent_success(client):
    r = client.post("/api/contact", json={**VALID, "website": "http://spam.bot"})
    assert r.status_code == 201
    assert r.json()["analysis"] is None


def test_idempotency_returns_cached(client):
    key = "test-idempotency-key-001"
    headers = {"Idempotency-Key": key}
    r1 = client.post("/api/contact", json=VALID, headers=headers)
    r2 = client.post("/api/contact", json=VALID, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["request_id"] == r2.json()["request_id"]


def test_public_health_is_minimal(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    assert "checks" not in body
    assert "ai_provider" not in body
    assert "ai_configured" not in body


def test_idempotency_conflict_on_different_body(client):
    key = "test-idempotency-key-002"
    headers = {"Idempotency-Key": key}
    r1 = client.post("/api/contact", json=VALID, headers=headers)
    r2 = client.post(
        "/api/contact",
        json={**VALID, "comment": "Другое сообщение для проверки конфликта"},
        headers=headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 409
    assert r2.json()["error"] == "idempotency_conflict"


def test_invalid_idempotency_key(client):
    r = client.post(
        "/api/contact",
        json=VALID,
        headers={"Idempotency-Key": "bad key with spaces and /slash"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_idempotency_key"


def test_overlong_idempotency_key_rejected(client):
    r = client.post(
        "/api/contact",
        json=VALID,
        headers={"Idempotency-Key": "K" * 65},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_idempotency_key"


def test_security_headers_present(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in r.headers


def test_metrics_open_without_token_in_development(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert "total_requests" in r.json()
