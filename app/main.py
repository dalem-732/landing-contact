"""Точка входа FastAPI-приложения."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import routes_contact, routes_health, routes_metrics
from app.core.config import CORS_ALLOWED_HEADERS, CORS_ALLOWED_METHODS, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db, init_db
from app.middleware.request_logging import RequestLoggingMiddleware

setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    logger.info(
        "Service started | env=%s | db=%s | ai_provider=%s | ai_configured=%s | smtp_configured=%s",
        settings.app_env,
        settings.masked_database_url,
        settings.ai_provider,
        settings.ai_configured,
        settings.smtp_configured,
    )
    yield
    await close_db()


settings = get_settings()

_docs_url = "/docs" if settings.docs_enabled else None
_redoc_url = "/redoc" if settings.docs_enabled else None
_openapi_url = "/openapi.json" if settings.docs_enabled else None

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Backend-сервис для лендинг-презентации разработчика: форма обратной связи "
        "с валидацией, email-уведомлениями, rate limiting и AI-анализом обращений."
    ),
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
    lifespan=lifespan,
    contact={
        "name": "Landing Contact Service",
        "email": settings.owner_email,
    },
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "contact", "description": "Форма обратной связи и публичная конфигурация"},
        {"name": "system", "description": "Health-check, метрики и служебные эндпоинты"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.effective_cors_credentials,
    allow_methods=CORS_ALLOWED_METHODS,
    allow_headers=CORS_ALLOWED_HEADERS,
)
app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)

app.include_router(routes_contact.router, prefix="/api", tags=["contact"])
app.include_router(routes_health.router, prefix="/api", tags=["system"])
app.include_router(routes_metrics.router, prefix="/api", tags=["system"])

FRONTEND_DIR = Path(settings.base_dir) / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
