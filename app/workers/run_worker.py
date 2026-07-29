"""Точка входа ARQ worker — env Railway уже доступен к моменту запуска."""
from arq.worker import run_worker

from app.workers.email_worker import create_worker_settings


if __name__ == "__main__":
    settings_cls = create_worker_settings()
    redis = settings_cls.redis_settings
    print(
        f"ARQ worker starting: redis={redis.host}:{redis.port}",
        flush=True,
    )
    run_worker(settings_cls)
