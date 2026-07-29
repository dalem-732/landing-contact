"""Тесты файлового rate limiter."""
from app.repositories.rate_limit_repository import RateLimitRepository


def test_allows_up_to_limit(tmp_path):
    repo = RateLimitRepository(
        path=tmp_path / "rl.json", max_requests=3, window_seconds=60
    )
    for _ in range(3):
        allowed, _remaining, _retry = repo.check("1.1.1.1")
        assert allowed is True


def test_blocks_after_limit(tmp_path):
    repo = RateLimitRepository(
        path=tmp_path / "rl.json", max_requests=2, window_seconds=60
    )
    repo.check("2.2.2.2")
    repo.check("2.2.2.2")
    allowed, remaining, retry_after = repo.check("2.2.2.2")
    assert allowed is False
    assert remaining == 0
    assert retry_after >= 1


def test_separate_ips_independent(tmp_path):
    repo = RateLimitRepository(
        path=tmp_path / "rl.json", max_requests=1, window_seconds=60
    )
    assert repo.check("3.3.3.3")[0] is True
    assert repo.check("4.4.4.4")[0] is True
    assert repo.check("3.3.3.3")[0] is False
