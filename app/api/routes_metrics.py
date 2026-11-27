"""Эндпоинт со статистикой обращений."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import require_metrics_token
from app.dependencies import get_metrics_repository, get_settings
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.system import MetricsResponse

router = APIRouter()


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Статистика обращений (требуется METRICS_TOKEN)",
)
async def metrics(
    request: Request,
    repo: MetricsRepository = Depends(get_metrics_repository),
    settings=Depends(get_settings),
) -> MetricsResponse:
    require_metrics_token(request, settings)
    data = await repo.snapshot()
    return MetricsResponse(**data)
