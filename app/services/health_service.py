"""Health probes для AI, SMTP, PostgreSQL и Redis."""
from __future__ import annotations

import asyncio
import smtplib

from sqlalchemy import text

from app.core.circuit_breaker import ai_circuit_breaker
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import get_engine

logger = get_logger("app.health")


class HealthService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def run_checks(self) -> dict:
        ai, smtp, postgres, redis_check = await asyncio.gather(
            self._check_ai(),
            asyncio.to_thread(self._check_smtp),
            self._check_postgres(),
            self._check_redis(),
        )
        checks = {"ai": ai, "smtp": smtp, "postgres": postgres, "redis": redis_check}
        statuses = [c["status"] for c in checks.values()]
        if all(s == "ok" for s in statuses):
            overall = "ok"
        elif any(s == "error" for s in statuses):
            overall = "degraded"
        else:
            overall = "degraded"
        return {"status": overall, "checks": checks}

    async def _check_ai(self) -> dict:
        if not self.settings.ai_configured:
            return {"status": "ok", "detail": "not configured (fallback mode)"}
        if ai_circuit_breaker.is_open:
            return {"status": "degraded", "detail": "circuit open"}
        return {"status": "ok", "detail": f"provider={self.settings.ai_provider}"}

    def _check_smtp(self) -> dict:
        if not self.settings.smtp_configured:
            return {"status": "ok", "detail": "not configured (fallback mode)"}
        try:
            with smtplib.SMTP(
                self.settings.smtp_host, self.settings.smtp_port, timeout=5
            ) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
            return {"status": "ok", "detail": "connection successful"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    async def _check_postgres(self) -> dict:
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ok", "detail": "connection successful"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    async def _check_redis(self) -> dict:
        if not self.settings.redis_url:
            return {"status": "ok", "detail": "not configured"}
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(self.settings.redis_url)
            await client.ping()
            await client.aclose()
            return {"status": "ok", "detail": "ping ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}


health_service = HealthService()
