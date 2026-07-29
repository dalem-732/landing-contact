"""Тесты SQL-агрегаций метрик."""
import pytest

from app.repositories.contact_repository import ContactRepository
from app.repositories.metrics_repository import MetricsRepository


@pytest.mark.asyncio
async def test_metrics_snapshot_from_contacts():
    contacts = ContactRepository()
    metrics = MetricsRepository()
    await contacts.append({
        "request_id": "m1",
        "client_ip": "1.1.1.1",
        "name": "A",
        "email": "a@test.com",
        "phone": "+79991234567",
        "comment": "Test message one",
        "status": "processing",
    })
    await contacts.update("m1", {
        "status": "processed",
        "sentiment": "positive",
        "category": "other",
        "ai_used": False,
    })
    snap = await metrics.snapshot()
    assert snap["total_requests"] == 1
    assert snap["by_sentiment"]["positive"] == 1
    assert snap["ai_fallback"] == 1
