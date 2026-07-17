"""Сервис rate limiting: dual-key (IP + email) с абстракцией backend."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.exceptions import RateLimitExceeded
from app.core.logging import get_logger

logger = get_logger("app.rate_limit")


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int = 0


class RateLimitBackend:
    def check(self, key: str, *, max_requests: int, window_seconds: int) -> RateLimitResult:
        raise NotImplementedError


class FileRateLimitBackend(RateLimitBackend):
    def __init__(self):
        from app.repositories.rate_limit_repository import RateLimitRepository
        self._repo = RateLimitRepository()

    def check(self, key: str, *, max_requests: int, window_seconds: int) -> RateLimitResult:
        allowed, remaining, retry_after = self._repo.check(
            key, max_requests=max_requests, window_seconds=window_seconds
        )
        return RateLimitResult(
            allowed=allowed,
            limit=max_requests,
            remaining=remaining,
            retry_after=retry_after,
        )


class RedisRateLimitBackend(RateLimitBackend):
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            import redis
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def check(self, key: str, *, max_requests: int, window_seconds: int) -> RateLimitResult:
        import time
        client = self._get_client()
        now = time.time()
        pipe_key = f"rl:{key}"
        pipe = client.pipeline()
        pipe.zremrangebyscore(pipe_key, 0, now - window_seconds)
        pipe.zadd(pipe_key, {str(now): now})
        pipe.zcard(pipe_key)
        pipe.expire(pipe_key, window_seconds + 1)
        _, _, count, _ = pipe.execute()
        if count > max_requests:
            oldest = client.zrange(pipe_key, 0, 0, withscores=True)
            retry_after = int(window_seconds - (now - oldest[0][1])) + 1 if oldest else window_seconds
            client.zrem(pipe_key, str(now))
            return RateLimitResult(False, max_requests, 0, max(retry_after, 1))
        return RateLimitResult(True, max_requests, max_requests - count)


def _resolve_backend(settings: Settings) -> RateLimitBackend:
    if settings.redis_url:
        try:
            return RedisRateLimitBackend(settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable for rate limit, using file backend: %s", exc)
    return FileRateLimitBackend()


class RateLimitService:
    def __init__(self, backend: RateLimitBackend | None = None):
        self._backend_override = backend

    def check(self, client_ip: str, email: str) -> RateLimitResult:
        settings = get_settings()
        backend = self._backend_override or _resolve_backend(settings)

        ip_result = backend.check(
            f"ip:{client_ip}",
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
        if not ip_result.allowed:
            raise RateLimitExceeded(retry_after=ip_result.retry_after, limit=ip_result.limit)

        email_result = backend.check(
            f"email:{email.lower()}",
            max_requests=settings.rate_limit_email_max,
            window_seconds=settings.rate_limit_email_window,
        )
        if not email_result.allowed:
            raise RateLimitExceeded(retry_after=email_result.retry_after, limit=email_result.limit)

        remaining = min(ip_result.remaining, email_result.remaining)
        return RateLimitResult(
            allowed=True,
            limit=ip_result.limit,
            remaining=remaining,
        )


rate_limit_service = RateLimitService()
