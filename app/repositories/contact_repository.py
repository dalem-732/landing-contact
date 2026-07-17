"""PostgreSQL repository for contact requests."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.core.logging import get_logger
from app.db.models.contact_request import ContactRequestModel
from app.db.session import get_session_factory

logger = get_logger("app.repo.contact")


class ContactRepository:
    async def append(self, record: dict) -> None:
        async with get_session_factory()() as session:
            row = ContactRequestModel(
                request_id=record["request_id"],
                client_ip=record["client_ip"],
                name=record["name"],
                email=record["email"],
                phone=record["phone"],
                comment=record["comment"],
                status=record.get("status", "processing"),
            )
            session.add(row)
            await session.commit()
        logger.debug("Stored contact request %s", record.get("request_id"))

    async def update(self, request_id: str, updates: dict) -> None:
        async with get_session_factory()() as session:
            updates = {**updates, "updated_at": datetime.now(timezone.utc)}
            result = await session.execute(
                update(ContactRequestModel)
                .where(ContactRequestModel.request_id == request_id)
                .values(**updates)
            )
            if result.rowcount == 0:
                logger.warning("Request %s not found for update", request_id)
            await session.commit()

    async def count(self) -> int:
        async with get_session_factory()() as session:
            result = await session.scalar(select(func.count()).select_from(ContactRequestModel))
            return int(result or 0)


contact_repository = ContactRepository()
