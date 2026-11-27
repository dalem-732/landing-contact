"""Проверка служебного токена для метрик и подробного health."""
from __future__ import annotations

import secrets

from fastapi import Request

from app.core.config import Settings
from app.core.exceptions import Unauthorized


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return (request.headers.get("x-metrics-token") or "").strip()


def require_metrics_token(request: Request, settings: Settings) -> None:
    expected = settings.metrics_token
    if not expected:
        if settings.app_env == "production" and settings.service_role != "worker":
            raise Unauthorized()
        return
    provided = _extract_token(request)
    if not provided or not secrets.compare_digest(provided, expected):
        raise Unauthorized()
