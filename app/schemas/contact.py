"""Pydantic-схемы формы обратной связи."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from enum import Enum

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings

_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё\s\-'.]{2,80}$")


def _sanitize(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch == "\n" or ch >= " ")
    return html.escape(cleaned.strip())


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class RequestCategory(str, Enum):
    job_offer = "job_offer"
    project_inquiry = "project_inquiry"
    collaboration = "collaboration"
    support = "support"
    spam = "spam"
    other = "other"


class ContactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=80, examples=["Иван Петров"])
    email: EmailStr = Field(..., examples=["ivan@example.com"])
    phone: str = Field(..., min_length=5, max_length=30, examples=["+7 999 123-45-67"])
    comment: str = Field(..., min_length=5, max_length=2000,
                         examples=["Здравствуйте! Хотел бы обсудить проект."])
    website: str | None = Field(
        default=None,
        description="Honeypot field — must be empty. Bots fill this in.",
    )
    captcha_token: str | None = Field(
        default=None,
        description="Cloudflare Turnstile token (required if TURNSTILE_SECRET_KEY is set).",
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not _NAME_RE.match(v):
            raise ValueError("Name contains invalid characters")
        return _sanitize(v)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        v = v.strip()
        region = get_settings().default_phone_region
        try:
            parsed = phonenumbers.parse(v, region)
        except phonenumbers.NumberParseException as exc:
            raise ValueError("Invalid phone number") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Invalid phone number")
        return phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )

    @field_validator("comment")
    @classmethod
    def _validate_comment(cls, v: str) -> str:
        return _sanitize(v)

    @property
    def is_honeypot_triggered(self) -> bool:
        return bool(self.website and self.website.strip())


class AIAnalysis(BaseModel):
    sentiment: Sentiment
    category: RequestCategory
    auto_reply: str
    summary: str
    ai_used: bool = Field(
        description="True, если ответ получен от AI-провайдера; False — fallback."
    )
    provider: str | None = None


class ContactResponse(BaseModel):
    success: bool = True
    message: str = "Спасибо! Ваше обращение принято."
    request_id: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysis: AIAnalysis | None = None
    email_owner_sent: bool | None = None
    email_user_sent: bool | None = None
    email_queued: bool = False


class ContactHandleResult(BaseModel):
    """Внутренний результат обработки с метаданными rate limit."""
    response: ContactResponse
    rate_limit_limit: int
    rate_limit_remaining: int
