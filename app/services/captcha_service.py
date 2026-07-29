"""Верификация Cloudflare Turnstile CAPTCHA."""
from __future__ import annotations

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("app.captcha")

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class CaptchaService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.turnstile_secret_key)

    async def verify(self, token: str | None, remote_ip: str | None = None) -> bool:
        if not self.configured:
            return True
        if not token:
            logger.info("Turnstile token missing")
            return False
        payload = {
            "secret": self.settings.turnstile_secret_key,
            "response": token,
        }
        if remote_ip:
            payload["remoteip"] = remote_ip
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(TURNSTILE_VERIFY_URL, data=payload)
                resp.raise_for_status()
                data = resp.json()
            ok = bool(data.get("success"))
            if not ok:
                logger.info("Turnstile verification failed: %s", data.get("error-codes"))
            return ok
        except Exception as exc:
            logger.warning("Turnstile verification error: %s", exc)
            return False


captcha_service = CaptchaService()
