"""Тесты глобальных обработчиков ошибок, CORS и production-валидации."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.exceptions import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware

VALID = {
    "name": "Иван Петров",
    "email": "ivan@example.com",
    "phone": "+7 999 123-45-67",
    "comment": "Здравствуйте! Хочу обсудить проект.",
}


@pytest.fixture
def handler_app():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    @app.get("/not-found")
    async def not_found():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    @app.get("/conflict")
    async def conflict():
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    return app


@pytest.fixture
def handler_client(handler_app):
    return TestClient(handler_app, raise_server_exceptions=False)


def test_validation_error_includes_request_id(client):
    r = client.post("/api/contact", json={**VALID, "email": "bad"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert "request_id" in body
    assert body["request_id"] == r.headers.get("X-Request-ID")


def test_rate_limit_error_includes_request_id(client, monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "1")
    from app.core import config
    config.get_settings.cache_clear()
    settings = config.get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    from app.main import app as main_app

    c = TestClient(main_app, raise_server_exceptions=False)
    c.post("/api/contact", json=VALID)
    r = c.post("/api/contact", json=VALID)
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "rate_limit_exceeded"
    assert "request_id" in body
    config.get_settings.cache_clear()


def test_404_includes_request_id(handler_client):
    r = handler_client.get("/not-found")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "not_found"
    assert "request_id" in body


def test_500_includes_request_id(handler_client):
    r = handler_client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "internal_error"
    assert "request_id" in body
    assert body["request_id"] == r.headers.get("X-Request-ID")


def test_integrity_error_returns_409(handler_client):
    r = handler_client.get("/conflict")
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "conflict"
    assert "request_id" in body


def test_cors_wildcard_disables_credentials():
    s = Settings(cors_origins="*", cors_allow_credentials=True)
    assert s.cors_is_wildcard
    assert s.effective_cors_credentials is False


def test_cors_explicit_origin_allows_credentials():
    s = Settings(cors_origins="https://example.com", cors_allow_credentials=True)
    assert s.effective_cors_credentials is True


def test_production_rejects_wildcard_cors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings()


def test_production_auto_cors_from_railway_domain(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "landing-contact-production.up.railway.app")
    s = Settings()
    assert s.cors_origins == "https://landing-contact-production.up.railway.app"


def test_production_worker_skips_cors_validation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "landing-worker")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    s = Settings()
    assert s.cors_origins == "*"
    assert s.service_role == "worker"


def test_production_requires_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings()


def test_docs_disabled_in_production():
    s = Settings(
        app_env="production",
        cors_origins="https://example.com",
        database_url="postgresql+asyncpg://u:p@localhost/db",
    )
    assert s.docs_enabled is False


def test_docs_enabled_in_development():
    s = Settings(app_env="development")
    assert s.docs_enabled is True


def test_database_url_normalized_for_asyncpg():
    s = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert s.database_url == "postgresql+asyncpg://user:pass@host:5432/db"
