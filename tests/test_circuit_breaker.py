"""Тесты circuit breaker для AI."""
import pytest

from app.core.circuit_breaker import CircuitBreaker
from app.schemas.contact import ContactRequest
from app.services.ai_service import AIService


def _request() -> ContactRequest:
    return ContactRequest(
        name="Иван", email="ivan@example.com",
        phone="+7 999 123-45-67", comment="Тестовое сообщение для проверки.",
    )


@pytest.mark.asyncio
async def test_circuit_opens_after_failures(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.core import config
    config.get_settings.cache_clear()

    breaker = CircuitBreaker("test", failure_threshold=2, cooldown_seconds=60)
    breaker.reset()
    service = AIService()

    async def fail_provider(_request):
        raise RuntimeError("AI down")

    monkeypatch.setattr(service, "_call_provider", fail_provider)
    monkeypatch.setattr("app.services.ai_service.ai_circuit_breaker", breaker)

    await service.analyze(_request())
    await service.analyze(_request())
    assert breaker.is_open

    # Third call should skip provider entirely.
    calls = {"count": 0}
    async def counted(_request):
        calls["count"] += 1
        raise RuntimeError("should not be called")

    monkeypatch.setattr(service, "_call_provider", counted)
    result = await service.analyze(_request())
    assert calls["count"] == 0
    assert result.ai_used is False
