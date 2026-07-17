"""PostgreSQL metrics via SQL aggregations over contact_requests."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.db.models.app_stat import AppStat
from app.db.models.contact_request import ContactRequestModel
from app.db.session import get_session_factory

logger = get_logger("app.repo.metrics")

CIRCUIT_STAT_KEY = "ai_circuit_open_count"


class MetricsRepository:
    async def snapshot(self) -> dict:
        async with get_session_factory()() as session:
            total = await session.scalar(
                select(func.count()).select_from(ContactRequestModel)
            ) or 0

            ai_used = await session.scalar(
                select(func.count()).where(ContactRequestModel.ai_used.is_(True))
            ) or 0

            email_queued = await session.scalar(
                select(func.count()).where(ContactRequestModel.email_queued.is_(True))
            ) or 0

            first_at = await session.scalar(
                select(func.min(ContactRequestModel.created_at))
            )
            last_at = await session.scalar(
                select(func.max(ContactRequestModel.created_at))
            )

            sentiment_rows = await session.execute(
                select(ContactRequestModel.sentiment, func.count())
                .where(ContactRequestModel.sentiment.is_not(None))
                .group_by(ContactRequestModel.sentiment)
            )
            category_rows = await session.execute(
                select(ContactRequestModel.category, func.count())
                .where(ContactRequestModel.category.is_not(None))
                .group_by(ContactRequestModel.category)
            )

            circuit_stat = await session.get(AppStat, CIRCUIT_STAT_KEY)
            circuit_count = circuit_stat.value if circuit_stat else 0

            return {
                "total_requests": int(total),
                "emails_sent_owner": 0,
                "emails_sent_user": 0,
                "emails_queued": int(email_queued),
                "ai_used": int(ai_used),
                "ai_fallback": int(total) - int(ai_used),
                "ai_circuit_open_count": circuit_count,
                "by_sentiment": {row[0]: row[1] for row in sentiment_rows.all()},
                "by_category": {row[0]: row[1] for row in category_rows.all()},
                "first_request_at": first_at.isoformat() if first_at else None,
                "last_request_at": last_at.isoformat() if last_at else None,
            }

    async def record_circuit_open(self) -> None:
        async with get_session_factory()() as session:
            stat = await session.get(AppStat, CIRCUIT_STAT_KEY)
            if stat:
                stat.value += 1
            else:
                session.add(AppStat(key=CIRCUIT_STAT_KEY, value=1))
            await session.commit()

    async def mark_email_queued(self, request_id: str) -> None:
        async with get_session_factory()() as session:
            from sqlalchemy import update
            await session.execute(
                update(ContactRequestModel)
                .where(ContactRequestModel.request_id == request_id)
                .values(email_queued=True)
            )
            await session.commit()


metrics_repository = MetricsRepository()
