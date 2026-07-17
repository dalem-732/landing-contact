"""Оркестрация полного цикла обработки обращения."""
from __future__ import annotations

import uuid

from fastapi import BackgroundTasks

from app.core.exceptions import CaptchaFailed
from app.core.logging import get_logger
from app.repositories.contact_repository import contact_repository
from app.repositories.idempotency_repository import idempotency_repository
from app.repositories.metrics_repository import metrics_repository
from app.schemas.contact import (
    ContactHandleResult,
    ContactRequest,
    ContactResponse,
)
from app.services.ai_service import ai_service
from app.services.captcha_service import captcha_service
from app.services.email_queue import email_queue_service
from app.services.rate_limit_service import rate_limit_service

logger = get_logger("app.service.contact")


class ContactService:
    def __init__(
        self,
        *,
        ai=ai_service,
        email_queue=email_queue_service,
        captcha=captcha_service,
        contacts=contact_repository,
        metrics=metrics_repository,
        rate_limiter=rate_limit_service,
        idempotency=idempotency_repository,
    ):
        self.ai = ai
        self.email_queue = email_queue
        self.captcha = captcha
        self.contacts = contacts
        self.metrics = metrics
        self.rate_limiter = rate_limiter
        self.idempotency = idempotency

    async def handle(
        self,
        request: ContactRequest,
        *,
        client_ip: str,
        idempotency_key: str | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> ContactHandleResult:
        if request.is_honeypot_triggered:
            logger.info("Honeypot triggered from %s", client_ip)
            fake_id = uuid.uuid4().hex[:12]
            return ContactHandleResult(
                response=ContactResponse(request_id=fake_id),
                rate_limit_limit=0,
                rate_limit_remaining=0,
            )

        payload_for_hash = request.model_dump(exclude={"website", "captcha_token"})
        body_hash = self.idempotency.body_hash(payload_for_hash)
        if idempotency_key:
            cached = await self.idempotency.get(idempotency_key, body_hash)
            if cached:
                logger.info("Idempotency hit for key %s", idempotency_key)
                return ContactHandleResult(
                    response=ContactResponse.model_validate(cached),
                    rate_limit_limit=0,
                    rate_limit_remaining=0,
                )

        rl = self.rate_limiter.check(client_ip, str(request.email))

        if not await self.captcha.verify(request.captcha_token, client_ip):
            raise CaptchaFailed()

        request_id = uuid.uuid4().hex[:12]
        logger.info("Processing contact request %s from %s", request_id, client_ip)

        await self.contacts.append({
            "request_id": request_id,
            "client_ip": client_ip,
            "name": request.name,
            "email": request.email,
            "phone": request.phone,
            "comment": request.comment,
            "status": "processing",
        })

        analysis = await self.ai.analyze(request)

        await self.contacts.update(request_id, {
            "sentiment": analysis.sentiment.value,
            "category": analysis.category.value,
            "summary": analysis.summary,
            "ai_used": analysis.ai_used,
            "ai_provider": analysis.provider,
            "status": "processed",
        })

        email_queued = await self.email_queue.enqueue(
            request, analysis, background_tasks=background_tasks
        )
        if email_queued:
            await self.metrics.mark_email_queued(request_id)

        response = ContactResponse(
            request_id=request_id,
            analysis=analysis,
            email_owner_sent=None,
            email_user_sent=None,
            email_queued=email_queued,
        )

        if idempotency_key:
            await self.idempotency.put(
                idempotency_key, body_hash, response.model_dump(mode="json")
            )

        return ContactHandleResult(
            response=response,
            rate_limit_limit=rl.limit,
            rate_limit_remaining=rl.remaining,
        )


contact_service = ContactService()
