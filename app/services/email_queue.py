"""Очередь отправки email: ARQ (Redis) или BackgroundTasks fallback."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import BackgroundTasks

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIAnalysis, ContactRequest

if TYPE_CHECKING:
    from arq import ArqRedis

logger = get_logger("app.email_queue")


class EmailQueueService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._pool: ArqRedis | None = None

    async def _get_pool(self):
        if self._pool is None and self.settings.redis_url:
            from arq import create_pool
            from arq.connections import RedisSettings
            self._pool = await create_pool(RedisSettings.from_dsn(self.settings.redis_url))
        return self._pool

    async def enqueue(
        self,
        request: ContactRequest,
        analysis: AIAnalysis,
        background_tasks: BackgroundTasks | None = None,
    ) -> bool:
        """Ставит отправку email в очередь. True = queued."""
        if self.settings.redis_url:
            try:
                pool = await self._get_pool()
                if pool:
                    await pool.enqueue_job(
                        "send_contact_emails",
                        request.model_dump(),
                        analysis.model_dump(),
                    )
                    logger.info("Email job enqueued via ARQ for %s", request.email)
                    return True
            except Exception as exc:
                logger.warning("ARQ enqueue failed, falling back to BackgroundTasks: %s", exc)

        if background_tasks is not None:
            from app.services.email_service import email_service
            background_tasks.add_task(
                email_service.send_notifications_sync,
                request,
                analysis,
            )
            logger.info("Email scheduled via BackgroundTasks for %s", request.email)
            return True

        # Last resort: sync send (should not happen in normal flow).
        from app.services.email_service import email_service
        email_service.send_notifications_sync(request, analysis)
        return False


email_queue_service = EmailQueueService()
