"""PostgreSQL repository for idempotency keys."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.core.logging import get_logger
from app.db.models.idempotency_key import IdempotencyKeyModel
from app.db.session import get_session_factory

logger = get_logger("app.repo.idempotency")

TTL_SECONDS = 86400


class IdempotencyRepository:
    @staticmethod
    def body_hash(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def _purge_expired(self, session) -> None:
        now = datetime.now(timezone.utc)
        await session.execute(
            delete(IdempotencyKeyModel).where(IdempotencyKeyModel.expires_at < now)
        )

    async def get(self, key: str, body_hash: str) -> dict | None:
        async with get_session_factory()() as session:
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(IdempotencyKeyModel).where(
                    IdempotencyKeyModel.key == key,
                    IdempotencyKeyModel.body_hash == body_hash,
                    IdempotencyKeyModel.expires_at > now,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return row.response

    async def put(self, key: str, body_hash: str, response: dict) -> None:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=TTL_SECONDS)
        async with get_session_factory()() as session:
            await self._purge_expired(session)
            existing = await session.get(IdempotencyKeyModel, key)
            if existing:
                existing.body_hash = body_hash
                existing.response = response
                existing.expires_at = expires
            else:
                session.add(
                    IdempotencyKeyModel(
                        key=key,
                        body_hash=body_hash,
                        response=response,
                        expires_at=expires,
                    )
                )
            await session.commit()
        logger.debug("Stored idempotency key %s", key)


idempotency_repository = IdempotencyRepository()
