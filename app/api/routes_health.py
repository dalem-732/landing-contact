"""Health-check эндпоинт с probes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app import __version__
from app.dependencies import get_health_service, get_settings
from app.schemas.system import HealthCheckDetail, HealthResponse
from app.services.health_service import HealthService

router = APIRouter()

_HEALTH_OK_EXAMPLE = {
    "status": "ok",
    "version": "1.0.0",
    "time": "2026-07-16T12:00:00Z",
    "ai_provider": "openai",
    "ai_configured": False,
    "smtp_configured": False,
    "checks": {
        "ai": {"status": "ok", "detail": "not configured (fallback mode)"},
        "smtp": {"status": "ok", "detail": "not configured (fallback mode)"},
        "postgres": {"status": "ok", "detail": "connection successful"},
        "redis": {"status": "ok", "detail": "not configured"},
    },
}

_HEALTH_DEGRADED_EXAMPLE = {
    **_HEALTH_OK_EXAMPLE,
    "status": "degraded",
    "checks": {
        **_HEALTH_OK_EXAMPLE["checks"],
        "smtp": {"status": "error", "detail": "connection refused"},
    },
}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Статус сервиса",
    responses={
        200: {
            "description": "Сервис работает",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {"value": _HEALTH_OK_EXAMPLE},
                        "degraded": {"value": _HEALTH_DEGRADED_EXAMPLE},
                    }
                }
            },
        }
    },
)
async def health(
    health_svc: HealthService = Depends(get_health_service),
    settings=Depends(get_settings),
) -> HealthResponse:
    probe = await health_svc.run_checks()
    checks = {
        name: HealthCheckDetail(**data)
        for name, data in probe["checks"].items()
    }
    return HealthResponse(
        status=probe["status"],
        version=__version__,
        time=datetime.now(timezone.utc),
        ai_provider=settings.ai_provider,
        ai_configured=settings.ai_configured,
        smtp_configured=settings.smtp_configured,
        checks=checks,
    )
