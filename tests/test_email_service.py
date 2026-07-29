"""Tests for email templates, Resend/SMTP providers, and delivery flags."""
from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.db.models.contact_request import ContactRequestModel
from app.repositories.contact_repository import contact_repository
from app.schemas.contact import (
    AIAnalysis,
    ContactRequest,
    RequestCategory,
    Sentiment,
)
from app.services import email_templates
from app.services.email_queue import send_and_record
from app.services.email_service import EmailService
from sqlalchemy import select

from app.db.session import get_session_factory


def _request(**overrides) -> ContactRequest:
    data = {
        "name": "Иван Петров",
        "email": "ivan@example.com",
        "phone": "+79991234567",
        "comment": "Хочу обсудить разработку API",
    }
    data.update(overrides)
    return ContactRequest(**data)


def _analysis(**overrides) -> AIAnalysis:
    data = {
        "sentiment": Sentiment.neutral,
        "category": RequestCategory.project_inquiry,
        "summary": "Интерес к API",
        "auto_reply": "Здравствуйте, Иван! Обсудим API на этой неделе.",
        "ai_used": True,
        "provider": "anthropic",
    }
    data.update(overrides)
    return AIAnalysis(**data)


def test_user_templates_include_auto_reply():
    req = _request()
    analysis = _analysis()
    plain = email_templates.user_plain(req, analysis)
    html = email_templates.user_html(req, analysis)
    assert analysis.auto_reply in plain
    assert "Обсудим API" in html
    assert req.comment in plain
    assert "Обращение принято" in html


def test_owner_templates_include_analysis():
    req = _request()
    analysis = _analysis()
    plain = email_templates.owner_plain(req, analysis)
    html = email_templates.owner_html(req, analysis)
    assert analysis.auto_reply in plain
    assert analysis.summary in html
    assert req.email in plain
    assert "project_inquiry" in html


def test_build_user_email_is_multipart_html():
    settings = Settings(smtp_from="Bot <onboarding@resend.dev>", owner_email="owner@example.com")
    svc = EmailService(settings)
    msg = svc._build_user_email(_request(), _analysis())
    assert msg.is_multipart()
    plain, html = svc._extract_bodies(msg)
    assert "Обсудим API" in plain
    assert html and "Обращение принято" in html


def test_send_logs_when_email_not_configured():
    settings = Settings(resend_api_key=None, smtp_host=None)
    svc = EmailService(settings)
    assert not settings.email_configured
    owner_sent, user_sent = svc.send_notifications_sync(_request(), _analysis())
    assert owner_sent is False
    assert user_sent is False


def test_send_via_resend(monkeypatch):
    settings = Settings(
        resend_api_key="re_test_key",
        smtp_from="Bot <onboarding@resend.dev>",
        owner_email="owner@example.com",
    )
    svc = EmailService(settings)
    assert settings.resend_configured
    assert settings.email_configured

    captured: list[dict] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            captured.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    owner_sent, user_sent = svc.send_notifications_sync(_request(), _analysis())
    assert owner_sent is True
    assert user_sent is True
    assert len(captured) == 2
    assert all(c["url"] == "https://api.resend.com/emails" for c in captured)
    assert all(
        c["headers"]["Authorization"] == "Bearer re_test_key" for c in captured
    )
    assert any(c["json"]["to"] == ["ivan@example.com"] for c in captured)
    assert any(c["json"]["to"] == ["owner@example.com"] for c in captured)
    user_payload = next(c["json"] for c in captured if c["json"]["to"] == ["ivan@example.com"])
    assert "Обсудим API" in user_payload["text"]
    assert "html" in user_payload
    assert "Обращение принято" in user_payload["html"]


def test_send_via_smtp_when_resend_missing(monkeypatch):
    settings = Settings(
        resend_api_key=None,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_use_tls=True,
        smtp_username="user",
        smtp_password="pass",
        smtp_from="Bot <noreply@example.com>",
        owner_email="owner@example.com",
    )
    svc = EmailService(settings)

    smtp_mock = MagicMock()
    smtp_mock.__enter__ = MagicMock(return_value=smtp_mock)
    smtp_mock.__exit__ = MagicMock(return_value=False)

    with patch("app.services.email_service.smtplib.SMTP", return_value=smtp_mock) as smtp_cls:
        owner_sent, user_sent = svc.send_notifications_sync(_request(), _analysis())

    assert owner_sent is True
    assert user_sent is True
    assert smtp_cls.call_count == 2
    assert smtp_mock.starttls.call_count == 2
    assert smtp_mock.login.call_count == 2
    assert smtp_mock.send_message.call_count == 2


def test_resend_preferred_over_smtp(monkeypatch):
    settings = Settings(
        resend_api_key="re_pref",
        smtp_host="smtp.example.com",
        smtp_from="Bot <onboarding@resend.dev>",
        owner_email="owner@example.com",
    )
    svc = EmailService(settings)

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
        owner_sent, user_sent = svc.send_notifications_sync(_request(), _analysis())

    assert owner_sent and user_sent
    smtp_cls.assert_not_called()


@pytest.mark.asyncio
async def test_send_and_record_updates_delivery_flags(monkeypatch):
    request_id = "abcdef123456"
    await contact_repository.append({
        "request_id": request_id,
        "client_ip": "127.0.0.1",
        "name": "Иван Петров",
        "email": "ivan@example.com",
        "phone": "+79991234567",
        "comment": "Хочу обсудить разработку API",
        "status": "processed",
    })

    settings = Settings(
        resend_api_key="re_test",
        smtp_from="Bot <onboarding@resend.dev>",
        owner_email="owner@example.com",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr("app.services.email_service.email_service", EmailService(settings))

    owner_sent, user_sent = await send_and_record(_request(), _analysis(), request_id)
    assert owner_sent is True
    assert user_sent is True

    async with get_session_factory()() as session:
        row = await session.scalar(
            select(ContactRequestModel).where(ContactRequestModel.request_id == request_id)
        )
        assert row is not None
        assert row.email_owner_sent is True
        assert row.email_user_sent is True
