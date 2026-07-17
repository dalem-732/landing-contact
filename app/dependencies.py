"""FastAPI dependency injection."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings as _get_settings
from app.db.session import get_session
from app.repositories.metrics_repository import MetricsRepository, metrics_repository
from app.services.ai_service import AIService, ai_service
from app.services.captcha_service import CaptchaService, captcha_service
from app.services.contact_service import ContactService, contact_service
from app.services.email_queue import EmailQueueService, email_queue_service
from app.services.health_service import HealthService, health_service
from app.services.rate_limit_service import RateLimitService, rate_limit_service


def get_settings() -> Settings:
    return _get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def get_contact_service() -> ContactService:
    return contact_service


def get_ai_service() -> AIService:
    return ai_service


def get_rate_limit_service() -> RateLimitService:
    return rate_limit_service


def get_captcha_service() -> CaptchaService:
    return captcha_service


def get_email_queue_service() -> EmailQueueService:
    return email_queue_service


def get_health_service() -> HealthService:
    return health_service


def get_metrics_repository() -> MetricsRepository:
    return metrics_repository
