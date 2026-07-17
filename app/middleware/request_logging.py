"""Middleware для логирования каждого HTTP-запроса в файл/консоль."""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.core.context import request_id_var
from app.core.logging import get_logger

logger = get_logger("app.request")


def client_ip(request: Request) -> str:
    """Определяет IP клиента с учётом доверенного обратного прокси."""
    settings = get_settings()
    direct = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and direct in settings.trusted_proxy_list:
        return forwarded.split(",")[0].strip()
    return direct


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        request.state.client_ip = client_ip(request)
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "rid=%s ip=%s %s %s -> 500 (%.1fms)",
                request_id, request.state.client_ip,
                request.method, request.url.path, elapsed_ms,
            )
            request_id_var.reset(token)
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "rid=%s ip=%s %s %s -> %s (%.1fms)",
            request_id, request.state.client_ip,
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
        response.headers["X-Request-ID"] = request_id
        request_id_var.reset(token)
        return response
