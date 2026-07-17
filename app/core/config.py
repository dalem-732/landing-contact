"""Конфигурация приложения на основе переменных окружения."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

AppEnv = Literal["development", "staging", "production"]
ServiceRole = Literal["web", "worker"]

CORS_ALLOWED_METHODS = ["GET", "POST", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Content-Type", "Idempotency-Key", "Authorization"]


def resolve_redis_url() -> str | None:
    """REDIS_URL или компоненты REDISHOST/… — Railway может отдавать оба формата."""
    for key in ("REDIS_URL", "REDIS_PRIVATE_URL", "REDIS_PUBLIC_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    host = os.environ.get("REDISHOST", "").strip()
    if not host:
        return None

    port = os.environ.get("REDISPORT", "6379").strip() or "6379"
    user = os.environ.get("REDISUSER", "default").strip() or "default"
    password = os.environ.get("REDISPASSWORD", "").strip()
    if password:
        return f"redis://{user}:{password}@{host}:{port}"
    return f"redis://{host}:{port}"


def redis_env_diagnostic() -> str:
    parts: list[str] = []
    for key in ("REDIS_URL", "REDIS_PRIVATE_URL", "REDIS_PUBLIC_URL", "REDISHOST"):
        if key not in os.environ:
            parts.append(f"{key}=<not set>")
        elif not os.environ[key].strip():
            parts.append(f"{key}=<EMPTY>")
        else:
            parts.append(f"{key}=<ok>")
    return ", ".join(parts)


class Settings(BaseSettings):
    """Все настройки сервиса. Значения читаются из .env / окружения."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Общие
    app_name: str = "Landing Contact Service"
    app_env: AppEnv = "development"
    service_role: ServiceRole = "web"
    debug: bool = True
    log_format: str = "text"  # text | json
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "*"
    cors_allow_credentials: bool = True

    # Trusted proxy (comma-separated IPs)
    trusted_proxy_ips: str = ""

    # Rate limiting — IP
    rate_limit_max_requests: int = 5
    rate_limit_window_seconds: int = 60
    rate_limit_email_max: int = 3
    rate_limit_email_window: int = 3600

    # Validation
    default_phone_region: str = "RU"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://landing:landing@localhost:5432/landing"
    db_pool_size: int = 5
    db_echo: bool = False

    # Redis
    redis_url: str | None = None

    # SMTP
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from: str = "Landing Bot <no-reply@example.com>"
    owner_email: str = "owner@example.com"

    # AI
    ai_provider: str = "openai"
    ai_timeout_seconds: int = 15
    ai_circuit_failure_threshold: int = 3
    ai_circuit_cooldown_seconds: int = 300
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"

    # Turnstile CAPTCHA
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None

    # Пути (не из env)
    base_dir: Path = Field(default=BASE_DIR, exclude=True)
    data_dir: Path = Field(default=DATA_DIR, exclude=True)
    logs_dir: Path = Field(default=LOGS_DIR, exclude=True)

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value):
        """Render/Railway отдают postgresql:// — SQLAlchemy async требует asyncpg."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("redis_url", mode="before")
    @classmethod
    def _resolve_redis_url(cls, value):
        if isinstance(value, str) and value.strip():
            return value
        return resolve_redis_url()

    @field_validator(
        "smtp_host", "smtp_username", "smtp_password",
        "openai_api_key", "anthropic_api_key",
        "turnstile_site_key", "turnstile_secret_key",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value):
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="before")
    @classmethod
    def _detect_service_role(cls, data):
        if not isinstance(data, dict):
            return data

        role = (data.get("service_role") or os.environ.get("SERVICE_ROLE") or "web").strip()
        if role == "web":
            railway_name = os.environ.get("RAILWAY_SERVICE_NAME", "").lower()
            if "worker" in railway_name:
                data["service_role"] = "worker"
        return data

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        if self.app_env == "production":
            if self.service_role != "worker" and self.cors_origins.strip() == "*":
                railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
                if railway_domain:
                    self.cors_origins = f"https://{railway_domain}"

            if self.service_role != "worker" and self.cors_origins.strip() == "*":
                raise ValueError("CORS_ORIGINS must not be '*' in production")
            if not self.database_url.strip():
                raise ValueError("DATABASE_URL is required in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def cors_is_wildcard(self) -> bool:
        return self.cors_origin_list == ["*"]

    @property
    def effective_cors_credentials(self) -> bool:
        """CORS spec forbids credentials with wildcard origin."""
        if self.cors_is_wildcard:
            return False
        return self.cors_allow_credentials

    @property
    def trusted_proxy_list(self) -> list[str]:
        raw = (self.trusted_proxy_ips or "").strip()
        if not raw:
            return []
        return [ip.strip() for ip in raw.split(",") if ip.strip()]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host)

    @property
    def ai_configured(self) -> bool:
        if self.ai_provider == "openai":
            return bool(self.openai_api_key)
        if self.ai_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return False

    @property
    def turnstile_configured(self) -> bool:
        return bool(self.turnstile_secret_key)

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"

    @property
    def masked_database_url(self) -> str:
        """DATABASE_URL без пароля — безопасно для логов."""
        try:
            parsed = urlparse(self.database_url)
            if parsed.password:
                host = parsed.hostname or ""
                if parsed.port:
                    host = f"{host}:{parsed.port}"
                netloc = f"{parsed.username}:****@{host}" if parsed.username else host
                return urlunparse(parsed._replace(netloc=netloc))
        except Exception:
            pass
        return self.database_url.split("@")[-1] if "@" in self.database_url else "***"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    return settings
