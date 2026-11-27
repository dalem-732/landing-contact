"""Health-check эндпоинты: публичный liveness и подробный probe."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app import __version__
from app.core.auth import require_metrics_token
from app.dependencies import get_health_service, get_settings
from app.schemas.system import HealthCheckDetail, HealthResponse, PublicHealthResponse
from app.services.health_service import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=PublicHealthResponse,
    summary="Публичный статус сервиса",
)
async def health(
    health_svc: HealthService = Depends(get_health_service),
) -> PublicHealthResponse:
    status = await health_svc.public_status()
    return PublicHealthResponse(
        status=status,
        version=__version__,
        time=datetime.now(timezone.utc),
    )


@router.get(
    "/health/details",
    response_model=HealthResponse,
    summary="Подробные health probes (требуется METRICS_TOKEN)",
)
async def health_details(
    request: Request,
    health_svc: HealthService = Depends(get_health_service),
    settings=Depends(get_settings),
) -> HealthResponse:
    require_metrics_token(request, settings)
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
        email_configured=settings.email_configured,
        checks=checks,
    )
