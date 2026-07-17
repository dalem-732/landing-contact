"""ARQ worker для отправки email."""
from __future__ import annotations

import os

from arq.connections import RedisSettings

from app.core.config import get_settings, redis_env_diagnostic, resolve_redis_url
from app.schemas.contact import AIAnalysis, ContactRequest
from app.services.email_service import email_service


async def send_contact_emails(ctx, request_data: dict, analysis_data: dict):
    request = ContactRequest.model_validate(request_data)
    analysis = AIAnalysis.model_validate(analysis_data)
    email_service.send_notifications_sync(request, analysis)


def _validate_redis_url(url: str) -> str:
    lowered = url.lower()
    is_local = any(token in lowered for token in ("localhost", "127.0.0.1", "[::1]", "::1"))
    on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_ID"))
    if is_local and on_railway:
        raise RuntimeError(
            "REDIS_URL указывает на localhost. "
            "landing-worker → Variables → Add Reference → Redis-сервис → REDIS_URL. "
            f"Diag: {redis_env_diagnostic()}"
        )
    return url


def _build_redis_settings() -> RedisSettings:
    url = resolve_redis_url() or get_settings().redis_url
    if not url:
        hint = (
            "REDIS_URL задан, но пустой — удалите переменную и создайте заново через "
            "Add Reference → ваш Redis-сервис → REDIS_URL (не вводите URL вручную)."
            if "REDIS_URL" in os.environ and not os.environ.get("REDIS_URL", "").strip()
            else "landing-worker → Variables → Add Reference → Redis-сервис → REDIS_URL."
        )
        raise RuntimeError(f"REDIS_URL is required for ARQ worker. {hint} Diag: {redis_env_diagnostic()}")
    return RedisSettings.from_dsn(_validate_redis_url(url))


def create_worker_settings():
    """Собирает WorkerSettings после inject env (Railway делает это при старте процесса)."""
    return type(
        "WorkerSettings",
        (),
        {
            "functions": [send_contact_emails],
            "redis_settings": _build_redis_settings(),
        },
    )


def __getattr__(name: str):
    if name == "WorkerSettings":
        return create_worker_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
