"""AI-сервис с circuit breaker и graceful fallback."""
from __future__ import annotations

import json
import re

from app.core.circuit_breaker import ai_circuit_breaker
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.repositories.metrics_repository import metrics_repository
from app.schemas.contact import (
    AIAnalysis,
    ContactRequest,
    RequestCategory,
    Sentiment,
)
from app.services.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = get_logger("app.ai")

_NEGATIVE_WORDS = {
    "плохо", "ужасно", "отвратительно", "разочарован", "жалоба", "проблема",
    "не работает", "обман", "верните", "bad", "terrible", "awful", "angry",
    "disappointed", "scam", "refund",
}
_POSITIVE_WORDS = {
    "спасибо", "отлично", "супер", "класс", "нравится", "рад", "здорово",
    "круто", "great", "awesome", "love", "excellent", "thanks", "amazing",
}
_SPAM_WORDS = {"http://", "https://", "casino", "viagra", "loan", "crypto", "bit.ly", "заработок"}
_JOB_WORDS = {"вакансия", "работа", "оффер", "зарплата", "hr", "job", "hiring", "position", "salary"}
_PROJECT_WORDS = {"проект", "сайт", "приложение", "разработ", "project", "app", "website", "build"}
_COLLAB_WORDS = {"сотрудничество", "партн", "collaborat", "partnership"}

_TAG_RE = re.compile(r"<[^>]*>")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]+\)")
_URL_RE = re.compile(
    r"(?i)(?:(?:https?|ftp|javascript|data):[^\s]+|//[^\s]+|"
    r"\bwww\.[^\s]+|"
    r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|ru|io|dev|info|xyz|app|site|link|co|cc|me|to|tv|top|online|shop|biz|pro)"
    r"(?:/[^\s]*)?)"
)
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().\-]{5,}\d)")
_DEFAULT_REPLY = "Спасибо за обращение, мы скоро свяжемся с вами."
MAX_AUTO_REPLY = 500


def _strip_phones(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        return "" if len(digits) >= 7 else match.group(0)

    return _PHONE_RE.sub(_repl, text)


def sanitize_auto_reply(text: str, fallback: str = _DEFAULT_REPLY) -> str:
    cleaned = _TAG_RE.sub("", text or "")
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _URL_RE.sub("", cleaned)
    cleaned = _EMAIL_RE.sub("", cleaned)
    cleaned = _strip_phones(cleaned)
    cleaned = _CTRL_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split()).strip()[:MAX_AUTO_REPLY]
    return cleaned or fallback


def _fallback_reply(name: str) -> str:
    return (
        f"Здравствуйте, {name}! Спасибо за ваше обращение. "
        "Я получил ваше сообщение и свяжусь с вами в ближайшее время."
    )


class AIService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def analyze(self, request: ContactRequest) -> AIAnalysis:
        if ai_circuit_breaker.is_open:
            logger.info("AI circuit open, using fallback")
            await metrics_repository.record_circuit_open()
            return self._fallback(request)

        if self.settings.ai_configured:
            try:
                data = await self._call_provider(request)
                ai_circuit_breaker.record_success()
                return self._build(data, ai_used=True, provider=self.settings.ai_provider, request=request)
            except Exception as exc:
                ai_circuit_breaker.record_failure()
                logger.warning("AI provider failed (%s), using fallback: %s",
                               self.settings.ai_provider, exc)
        else:
            logger.info("AI not configured, using heuristic fallback")

        return self._fallback(request)

    async def _call_provider(self, request: ContactRequest) -> dict:
        prompt = USER_PROMPT_TEMPLATE.format(
            name=request.name, email=request.email, comment=request.comment
        )
        if self.settings.ai_provider == "anthropic":
            raw = await self._call_anthropic(prompt)
        else:
            raw = await self._call_openai(prompt)
        return self._parse_json(raw)

    async def _call_openai(self, prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.ai_timeout_seconds,
        )
        resp = await client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or ""

    async def _call_anthropic(self, prompt: str) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(
            api_key=self.settings.anthropic_api_key,
            timeout=self.settings.ai_timeout_seconds,
        )
        resp = await client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]
        return json.loads(raw)

    def _build(self, data: dict, *, ai_used: bool, provider: str | None, request: ContactRequest) -> AIAnalysis:
        return AIAnalysis(
            sentiment=self._coerce(data.get("sentiment"), Sentiment, Sentiment.neutral),
            category=self._coerce(data.get("category"), RequestCategory, RequestCategory.other),
            summary=(data.get("summary") or "").strip()[:300] or "Без резюме",
            auto_reply=sanitize_auto_reply(data.get("auto_reply") or "", fallback=""),
            ai_used=ai_used,
            provider=provider,
        )

    @staticmethod
    def _coerce(value, enum_cls, default):
        try:
            return enum_cls(value)
        except (ValueError, KeyError, TypeError):
            return default

    def _fallback(self, request: ContactRequest) -> AIAnalysis:
        text = f"{request.comment}".lower()

        sentiment = Sentiment.neutral
        if any(w in text for w in _NEGATIVE_WORDS):
            sentiment = Sentiment.negative
        elif any(w in text for w in _POSITIVE_WORDS):
            sentiment = Sentiment.positive

        if any(w in text for w in _SPAM_WORDS):
            category = RequestCategory.spam
        elif any(w in text for w in _JOB_WORDS):
            category = RequestCategory.job_offer
        elif any(w in text for w in _PROJECT_WORDS):
            category = RequestCategory.project_inquiry
        elif any(w in text for w in _COLLAB_WORDS):
            category = RequestCategory.collaboration
        else:
            category = RequestCategory.other

        summary = request.comment.strip().split("\n")[0][:120]
        auto_reply = sanitize_auto_reply(_fallback_reply(request.name))

        return AIAnalysis(
            sentiment=sentiment,
            category=category,
            summary=summary or "Без резюме",
            auto_reply=auto_reply,
            ai_used=False,
            provider=None,
        )


ai_service = AIService()
