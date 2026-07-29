"""Контроллер формы обратной связи."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from app.dependencies import get_contact_service, get_settings
from app.middleware.request_logging import client_ip
from app.schemas.contact import ContactRequest, ContactResponse
from app.schemas.system import PublicConfigResponse
from app.services.contact_service import ContactService

router = APIRouter()

_VALIDATION_ERROR_EXAMPLE = {
    "success": False,
    "error": "validation_error",
    "message": "Request validation failed",
    "status": 422,
    "request_id": "a1b2c3d4e5f6",
    "detail": [
        {"field": "email", "message": "value is not a valid email address", "type": "value_error"}
    ],
}

_RATE_LIMIT_ERROR_EXAMPLE = {
    "success": False,
    "error": "rate_limit_exceeded",
    "message": "Too many requests. Please try again later.",
    "status": 429,
    "request_id": "a1b2c3d4e5f6",
}

_CAPTCHA_ERROR_EXAMPLE = {
    "success": False,
    "error": "captcha_failed",
    "message": "CAPTCHA verification failed",
    "status": 400,
    "request_id": "a1b2c3d4e5f6",
}

_INTERNAL_ERROR_EXAMPLE = {
    "success": False,
    "error": "internal_error",
    "message": "Internal server error",
    "status": 500,
    "request_id": "a1b2c3d4e5f6",
}

_SUCCESS_EXAMPLE = {
    "success": True,
    "message": "Спасибо! Ваше обращение принято.",
    "request_id": "req-abc123",
    "received_at": "2026-07-16T12:00:00Z",
    "analysis": {
        "sentiment": "positive",
        "category": "project_inquiry",
        "auto_reply": "Спасибо за обращение!",
        "summary": "Клиент интересуется проектом",
        "ai_used": False,
        "provider": None,
    },
    "email_owner_sent": None,
    "email_user_sent": None,
    "email_queued": True,
}


@router.get(
    "/config/public",
    response_model=PublicConfigResponse,
    summary="Публичная конфигурация для фронтенда",
    responses={
        200: {
            "description": "Публичные настройки для клиента",
            "content": {
                "application/json": {
                    "example": {
                        "turnstile_site_key": "0x4AAAAAAA...",
                        "turnstile_enabled": True,
                    }
                }
            },
        }
    },
)
async def public_config(settings=Depends(get_settings)) -> PublicConfigResponse:
    return PublicConfigResponse(
        turnstile_site_key=settings.turnstile_site_key,
        turnstile_enabled=settings.turnstile_configured,
    )


@router.post(
    "/contact",
    status_code=status.HTTP_201_CREATED,
    summary="Отправить обращение через форму обратной связи",
    responses={
        201: {
            "description": "Обращение принято и обработано",
            "content": {"application/json": {"example": _SUCCESS_EXAMPLE}},
        },
        400: {
            "description": "CAPTCHA verification failed",
            "content": {"application/json": {"example": _CAPTCHA_ERROR_EXAMPLE}},
        },
        422: {
            "description": "Ошибка валидации",
            "content": {"application/json": {"example": _VALIDATION_ERROR_EXAMPLE}},
        },
        429: {
            "description": "Rate limit",
            "content": {"application/json": {"example": _RATE_LIMIT_ERROR_EXAMPLE}},
        },
        500: {
            "description": "Internal server error",
            "content": {"application/json": {"example": _INTERNAL_ERROR_EXAMPLE}},
        },
    },
)
async def create_contact(
    payload: ContactRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    service: ContactService = Depends(get_contact_service),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Полный цикл: валидация -> rate limit -> captcha -> save -> AI -> email queue -> ответ."""
    ip = getattr(request.state, "client_ip", None) or client_ip(request)
    result = await service.handle(
        payload,
        client_ip=ip,
        idempotency_key=idempotency_key,
        background_tasks=background_tasks,
    )
    headers = {}
    if result.rate_limit_limit:
        headers["X-RateLimit-Limit"] = str(result.rate_limit_limit)
        headers["X-RateLimit-Remaining"] = str(result.rate_limit_remaining)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=result.response.model_dump(mode="json"),
        headers=headers,
    )
