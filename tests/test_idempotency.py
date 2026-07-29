"""Тесты idempotency repository."""
import pytest

from app.repositories.idempotency_repository import IdempotencyRepository


@pytest.mark.asyncio
async def test_idempotency_store_and_retrieve():
    repo = IdempotencyRepository()
    payload = {"name": "Ivan", "email": "a@b.com"}
    h = repo.body_hash(payload)
    await repo.put("key1", h, {"request_id": "abc", "success": True})
    cached = await repo.get("key1", h)
    assert cached["request_id"] == "abc"


@pytest.mark.asyncio
async def test_idempotency_different_body():
    repo = IdempotencyRepository()
    h1 = repo.body_hash({"a": 1})
    h2 = repo.body_hash({"a": 2})
    await repo.put("key1", h1, {"request_id": "abc"})
    assert await repo.get("key1", h2) is None
