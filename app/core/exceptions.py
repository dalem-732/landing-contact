"""Кастомные исключения и глобальные обработчики ошибок."""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("app.errors")


class AppError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, *, detail=None, limit: int | None = None):
        self.message = message or self.message
        self.detail = detail
        self.limit = limit
        super().__init__(self.message)


class RateLimitExceeded(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"
    message = "Too many requests. Please try again later."

    def __init__(self, retry_after: int, message: str | None = None, limit: int | None = None):
        self.retry_after = retry_after
        super().__init__(message, limit=limit)


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"
    message = "Request validation failed"


class CaptchaFailed(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "captcha_failed"
    message = "CAPTCHA verification failed"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_body(
    error_code: str,
    message: str,
    status_code: int,
    detail=None,
    request_id: str | None = None,
) -> dict:
    body = {
        "success": False,
        "error": error_code,
        "message": message,
        "status": status_code,
    }
    if request_id:
        body["request_id"] = request_id
    if detail is not None:
        body["detail"] = detail
    return body


def _error_response(
    error_code: str,
    message: str,
    status_code: int,
    request: Request,
    detail=None,
    headers: dict | None = None,
) -> JSONResponse:
    rid = _request_id(request)
    merged_headers = dict(headers or {})
    if rid:
        merged_headers["X-Request-ID"] = rid
    return JSONResponse(
        status_code=status_code,
        content=_error_body(error_code, message, status_code, detail, rid),
        headers=merged_headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError):
        logger.warning("AppError [%s]: %s", exc.error_code, exc.message)
        headers = {}
        if isinstance(exc, RateLimitExceeded):
            headers["Retry-After"] = str(exc.retry_after)
            if exc.limit is not None:
                headers["X-RateLimit-Limit"] = str(exc.limit)
                headers["X-RateLimit-Remaining"] = "0"
        return _error_response(
            exc.error_code, exc.message, exc.status_code, request, exc.detail, headers
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
                "message": err.get("msg"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        logger.info("Validation error on %s: %s", request.url.path, errors)
        return _error_response(
            "validation_error",
            "Request validation failed",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            request,
            errors,
        )

    @app.exception_handler(IntegrityError)
    async def _handle_integrity(request: Request, exc: IntegrityError):
        logger.warning("IntegrityError on %s: %s", request.url.path, exc)
        return _error_response(
            "conflict",
            "Resource conflict (duplicate or constraint violation)",
            status.HTTP_409_CONFLICT,
            request,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException):
        error_code = "not_found" if exc.status_code == 404 else "http_error"
        return _error_response(error_code, str(exc.detail), exc.status_code, request)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s: %s", request.url.path, exc)
        return _error_response(
            "internal_error",
            "Internal server error",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            request,
        )
