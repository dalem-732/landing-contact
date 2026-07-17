"""Тесты PostgreSQL contact repository."""
import pytest

from app.repositories.contact_repository import ContactRepository


@pytest.mark.asyncio
async def test_contact_create_and_update():
    repo = ContactRepository()
    await repo.append({
        "request_id": "abc123",
        "client_ip": "127.0.0.1",
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+79991234567",
        "comment": "Hello world test",
        "status": "processing",
    })
    await repo.update("abc123", {"status": "processed", "sentiment": "neutral"})
    assert await repo.count() == 1
