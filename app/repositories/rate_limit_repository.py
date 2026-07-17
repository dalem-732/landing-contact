"""Файловый rate limiter: скользящее окно по IP-адресу."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.repo.ratelimit")
_lock = threading.Lock()


class RateLimitRepository:
    def __init__(self, path: Path | None = None,
                 max_requests: int | None = None,
                 window_seconds: int | None = None):
        self._path_override = path
        settings = get_settings()
        self.max_requests = max_requests or settings.rate_limit_max_requests
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds

    @property
    def path(self) -> Path:
        if self._path_override is not None:
            return self._path_override
        return get_settings().data_dir / "rate_limit.json"

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f)
        tmp.replace(self.path)

    def check(
        self,
        identifier: str,
        *,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> tuple[bool, int, int]:
        """Регистрирует попытку.

        Возвращает (allowed, remaining, retry_after_seconds).
        """
        limit = max_requests if max_requests is not None else self.max_requests
        window = window_seconds if window_seconds is not None else self.window_seconds
        now = time.time()
        window_start = now - window
        with _lock:
            data = self._read()
            timestamps = [t for t in data.get(identifier, []) if t > window_start]

            if len(timestamps) >= limit:
                retry_after = int(timestamps[0] + window - now) + 1
                data[identifier] = timestamps
                self._prune(data, window_start)
                self._write(data)
                logger.info("Rate limit hit for %s", identifier)
                return False, 0, max(retry_after, 1)

            timestamps.append(now)
            data[identifier] = timestamps
            self._prune(data, window_start)
            self._write(data)
            remaining = limit - len(timestamps)
            return True, remaining, 0

    @staticmethod
    def _prune(data: dict, window_start: float) -> None:
        """Удаляет пустые записи, чтобы файл не рос бесконечно."""
        for key in list(data.keys()):
            data[key] = [t for t in data[key] if t > window_start]
            if not data[key]:
                del data[key]


rate_limit_repository = RateLimitRepository()
