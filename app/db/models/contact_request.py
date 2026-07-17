"""ORM model for contact form submissions."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContactRequestModel(Base):
    __tablename__ = "contact_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_queued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
