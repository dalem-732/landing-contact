"""Response schemas for system API endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthCheckDetail(BaseModel):
    status: str
    detail: str


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok", "degraded"])
    version: str
    time: datetime
    ai_provider: str
    ai_configured: bool
    smtp_configured: bool
    checks: dict[str, HealthCheckDetail]


class MetricsResponse(BaseModel):
    total_requests: int
    emails_sent_owner: int = 0
    emails_sent_user: int = 0
    emails_queued: int = 0
    ai_used: int = 0
    ai_fallback: int = 0
    ai_circuit_open_count: int = 0
    by_sentiment: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    first_request_at: str | None = None
    last_request_at: str | None = None


class PublicConfigResponse(BaseModel):
    turnstile_site_key: str | None = None
    turnstile_enabled: bool
