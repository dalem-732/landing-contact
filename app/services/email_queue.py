"""Очередь отправки email: ARQ (Redis) или BackgroundTasks fallback."""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import BackgroundTasks

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIAnalysis, ContactRequest

if TYPE_CHECKING:
    from arq import ArqRedis

logger = get_logger("app.email_queue")


async def send_and_record(
    request: ContactRequest,
    analysis: AIAnalysis,
    request_id: str | None = None,
) -> tuple[bool, bool]:
    """Отправка + запись email_owner_sent / email_user_sent в БД.

    Получатель с уже сохранённым ``True`` пропускается: повтор задачи ARQ
    не отправляет письмо, которое уже ушло. Флаг пишется сразу после каждой
    попытки, чтобы сбой на втором письме не стирал успех первого.
    """
    from app.repositories.contact_repository import contact_repository
    from app.services.email_service import email_service

    skip_owner = False
    skip_user = False
    if request_id:
        existing = await contact_repository.get_email_flags(request_id)
        if existing is not None:
            skip_owner = existing[0] is True
            skip_user = existing[1] is True

    if skip_owner and skip_user:
        return True, True

    if (
        not email_service.settings.email_configured
        and not skip_owner
        and not skip_user
    ):
        owner_sent, user_sent = email_service.send_notifications_sync(request, analysis)
        if request_id:
            await contact_repository.update(
                request_id,
                {
                    "email_owner_sent": owner_sent,
                    "email_user_sent": user_sent,
                },
            )
        return owner_sent, user_sent

    owner_sent = True
    user_sent = True
    # Стабильный ключ на заявку и получателя: повтор задачи не дублирует письмо,
    # которое Resend уже принял (таймаут клиента после фактической отправки).
    owner_key = f"contact/{request_id}/owner" if request_id else None
    user_key = f"contact/{request_id}/user" if request_id else None
    if not skip_owner:
        owner_sent = email_service.send_owner_notification(
            request, analysis, idempotency_key=owner_key
        )
        if request_id:
            await contact_repository.update(
                request_id, {"email_owner_sent": owner_sent}
            )
    if not skip_user:
        user_sent = email_service.send_user_notification(
            request, analysis, idempotency_key=user_key
        )
        if request_id:
            await contact_repository.update(
                request_id, {"email_user_sent": user_sent}
            )
    return owner_sent, user_sent


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
        *,
        request_id: str | None = None,
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
                        request_id,
                    )
                    logger.info("Email job enqueued via ARQ for %s", request.email)
                    return True
            except Exception as exc:
                logger.warning("ARQ enqueue failed, falling back to BackgroundTasks: %s", exc)

        if background_tasks is not None:
            background_tasks.add_task(send_and_record, request, analysis, request_id)
            logger.info("Email scheduled via BackgroundTasks for %s", request.email)
            return True

        await send_and_record(request, analysis, request_id)
        return False


email_queue_service = EmailQueueService()
