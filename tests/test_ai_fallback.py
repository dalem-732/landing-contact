"""Тесты AI-сервиса в режиме fallback (без внешнего провайдера)."""
import pytest

from app.schemas.contact import ContactRequest, RequestCategory, Sentiment
from app.services.ai_service import AIService


def _request(comment: str) -> ContactRequest:
    return ContactRequest(
        name="Иван Петров", email="ivan@example.com",
        phone="+7 999 123-45-67", comment=comment,
    )


@pytest.mark.asyncio
async def test_fallback_used_without_key():
    service = AIService()  # ключи не заданы в тестовом окружении
    result = await service.analyze(_request("Спасибо, отличный сервис!"))
    assert result.ai_used is False
    assert result.provider is None
    assert result.auto_reply


@pytest.mark.asyncio
async def test_fallback_positive_sentiment():
    service = AIService()
    result = await service.analyze(_request("Спасибо большое, всё супер!"))
    assert result.sentiment == Sentiment.positive


@pytest.mark.asyncio
async def test_fallback_negative_sentiment():
    service = AIService()
    result = await service.analyze(_request("Это ужасно, ничего не работает"))
    assert result.sentiment == Sentiment.negative


@pytest.mark.asyncio
async def test_fallback_job_category():
    service = AIService()
    result = await service.analyze(_request("У нас открыта вакансия, готовы обсудить оффер"))
    assert result.category == RequestCategory.job_offer
