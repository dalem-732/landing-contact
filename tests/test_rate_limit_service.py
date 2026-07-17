"""Тесты dual-key rate limit service."""
import pytest

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceeded
from app.repositories.rate_limit_repository import RateLimitRepository
from app.services.rate_limit_service import FileRateLimitBackend, RateLimitService


def test_dual_key_independent_limits(monkeypatch, tmp_path):
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "10")
    monkeypatch.setenv("RATE_LIMIT_EMAIL_MAX", "1")
    get_settings.cache_clear()
    backend = FileRateLimitBackend()
    backend._repo = RateLimitRepository(path=tmp_path / "rate_limit.json")
    svc = RateLimitService(backend=backend)

    r1 = svc.check("1.1.1.1", "a@test.com")
    assert r1.allowed

    with pytest.raises(RateLimitExceeded):
        svc.check("2.2.2.2", "a@test.com")

    get_settings.cache_clear()
