"""Общая настройка тестов: in-memory SQLite DB + изолированные каталоги."""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import close_db, get_engine, reset_db_state
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir()
    logs_dir.mkdir()

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr(settings, "logs_dir", logs_dir)

    yield

    get_settings.cache_clear()
    reset_db_state()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(isolated_env):
    reset_db_state()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    reset_db_state()
