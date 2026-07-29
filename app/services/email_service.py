"""Email-сервис: Resend (preferred) → SMTP → log fallback."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIAnalysis, ContactRequest
from app.services import email_templates

logger = get_logger("app.email")

RESEND_API_URL = "https://api.resend.com/emails"


class EmailService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def send_notifications_sync(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> tuple[bool, bool]:
        """Синхронная отправка (вызывается из BackgroundTasks / ARQ worker)."""
        owner_msg = self._build_owner_email(request, analysis)
        user_msg = self._build_user_email(request, analysis)

        if not self.settings.email_configured:
            logger.warning("Email not configured — messages logged instead of sent")
            self._log_email("OWNER", owner_msg)
            self._log_email("USER", user_msg)
            return False, False

        owner_sent = self._send(owner_msg)
        user_sent = self._send(user_msg)
        return owner_sent, user_sent

    def _send(self, msg: EmailMessage) -> bool:
        if self.settings.resend_configured:
            return self._send_resend(msg)
        return self._send_smtp(msg)

    def _send_resend(self, msg: EmailMessage) -> bool:
        plain, html_body = self._extract_bodies(msg)
        payload: dict = {
            "from": str(msg["From"]),
            "to": [str(msg["To"])],
            "subject": str(msg["Subject"]),
            "text": plain,
        }
        if html_body:
            payload["html"] = html_body
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
            logger.info("Email sent via Resend to %s", msg["To"])
            return True
        except Exception as exc:
            logger.error("Failed to send email via Resend to %s: %s", msg["To"], exc)
            self._log_email("FALLBACK", msg)
            return False

    def _send_smtp(self, msg: EmailMessage) -> bool:
        try:
            with smtplib.SMTP(
                self.settings.smtp_host, self.settings.smtp_port, timeout=15
            ) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(msg)
            logger.info("Email sent via SMTP to %s", msg["To"])
            return True
        except Exception as exc:
            logger.error("Failed to send email via SMTP to %s: %s", msg["To"], exc)
            self._log_email("FALLBACK", msg)
            return False

    def _build_owner_email(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"Новое обращение с лендинга: {analysis.category.value}"
        msg["From"] = self.settings.smtp_from
        msg["To"] = self.settings.owner_email
        plain = email_templates.owner_plain(request, analysis)
        html_body = email_templates.owner_html(request, analysis)
        msg.set_content(plain)
        msg.add_alternative(html_body, subtype="html")
        return msg

    def _build_user_email(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = "Ваше обращение принято"
        msg["From"] = self.settings.smtp_from
        msg["To"] = str(request.email)
        plain = email_templates.user_plain(request, analysis)
        html_body = email_templates.user_html(request, analysis)
        msg.set_content(plain)
        msg.add_alternative(html_body, subtype="html")
        return msg

    @staticmethod
    def _extract_bodies(msg: EmailMessage) -> tuple[str, str | None]:
        plain = ""
        html_body: str | None = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                ctype = part.get_content_type()
                try:
                    content = part.get_content()
                except Exception:
                    continue
                if not isinstance(content, str):
                    continue
                if ctype == "text/plain" and not plain:
                    plain = content
                elif ctype == "text/html":
                    html_body = content
        else:
            content = msg.get_content()
            plain = content if isinstance(content, str) else ""
        return plain, html_body

    @staticmethod
    def _log_email(kind: str, msg: EmailMessage) -> None:
        plain, _ = EmailService._extract_bodies(msg)
        logger.info(
            "[EMAIL:%s] to=%s subject=%s\n%s",
            kind, msg["To"], msg["Subject"], plain,
        )


email_service = EmailService()
