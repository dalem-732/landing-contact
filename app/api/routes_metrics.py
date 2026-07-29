"""Эндпоинт со статистикой обращений."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_metrics_repository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.system import MetricsResponse

router = APIRouter()

_METRICS_EXAMPLE = {
    "total_requests": 42,
    "emails_sent_owner": 40,
    "emails_sent_user": 38,
    "emails_queued": 2,
    "ai_used": 30,
    "ai_fallback": 12,
    "ai_circuit_open_count": 0,
    "by_sentiment": {"positive": 20, "neutral": 15, "negative": 7},
    "by_category": {"project_inquiry": 25, "job_offer": 10, "other": 7},
    "first_request_at": "2026-07-01T10:00:00Z",
    "last_request_at": "2026-07-16T12:00:00Z",
}


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Статистика обращений",
    responses={
        200: {
            "description": "Агрегированная статистика",
            "content": {"application/json": {"example": _METRICS_EXAMPLE}},
        }
    },
)
async def metrics(repo: MetricsRepository = Depends(get_metrics_repository)) -> MetricsResponse:
    """Агрегированная статистика из PostgreSQL (contact_requests)."""
    data = await repo.snapshot()
    return MetricsResponse(**data)
