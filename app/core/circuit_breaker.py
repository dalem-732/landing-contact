"""In-memory circuit breaker для внешних вызовов (AI)."""
from __future__ import annotations

import time
import threading

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.circuit_breaker")
_lock = threading.Lock()


class CircuitBreaker:
    def __init__(self, name: str, *, failure_threshold: int, cooldown_seconds: int):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self.open_count = 0

    @property
    def is_open(self) -> bool:
        with _lock:
            if self._opened_at is None:
                return False
            if time.time() - self._opened_at >= self.cooldown_seconds:
                self._opened_at = None
                self._failures = 0
                logger.info("Circuit '%s' half-open (cooldown elapsed)", self.name)
                return False
            return True

    def record_success(self) -> None:
        with _lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with _lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                if self._opened_at is None:
                    self._opened_at = time.time()
                    self.open_count += 1
                    logger.warning(
                        "Circuit '%s' opened after %d failures",
                        self.name, self._failures,
                    )

    def reset(self) -> None:
        with _lock:
            self._failures = 0
            self._opened_at = None


def get_ai_circuit_breaker() -> CircuitBreaker:
    settings = get_settings()
    return CircuitBreaker(
        "ai",
        failure_threshold=settings.ai_circuit_failure_threshold,
        cooldown_seconds=settings.ai_circuit_cooldown_seconds,
    )


ai_circuit_breaker = get_ai_circuit_breaker()
