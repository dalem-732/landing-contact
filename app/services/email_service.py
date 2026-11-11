"""Email-сервис: Resend → SMTP → лог.

На каждое письмо:
1. Resend, если задан ``RESEND_API_KEY``.
2. При ошибке Resend (исключение, таймаут, не-2xx) — SMTP, если задан ``SMTP_HOST``.
3. Иначе тело пишется в лог как ``[EMAIL:FALLBACK]``, отправка считается неуспешной.

Временные сбои (сеть, таймаут, HTTP 5xx/429/409, временные SMTP 4xx) повторяются
несколько раз с паузой. Прочие HTTP 4xx и постоянные SMTP 5xx не повторяются.
Успешный канал дальше не вызывается. Повтор в Resend использует тот же
``Idempotency-Key`` (на обращение и получателя), поэтому таймаут после
фактической отправки не создаёт второе письмо.
"""
from __future__ import annotations

import smtplib
import time
import uuid
from email.message import EmailMessage

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIAnalysis, ContactRequest
from app.services import email_templates

logger = get_logger("app.email")

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT_SECONDS = 15.0
SMTP_TIMEOUT_SECONDS = 15
# Первая попытка сразу, затем паузы между повторами.
MAX_DELIVERY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1.0, 2.0)


def _resend_error_is_transient(exc: Exception) -> bool:
    """Сеть, таймаут, HTTP 429/5xx и 409.

    409 — параллельный запрос с тем же Idempotency-Key: Resend просит
    повторить позже. Прочие HTTP 4xx (неверный ключ, 422) не повторяются.
    """
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code in (409, 429) or code >= 500
    return False


def _smtp_error_is_transient(exc: Exception) -> bool:
    """Обрыв соединения и временные ответы SMTP (4xx). Постоянные 5xx — нет.

    ``SMTPException`` наследует ``OSError``, поэтому код ответа проверяется
    раньше, чем тип ``OSError``: иначе 535/550 тоже считались бы временными.
    """
    code = getattr(exc, "smtp_code", None)
    if isinstance(code, int):
        return 400 <= code < 500
    if isinstance(exc, (TimeoutError, smtplib.SMTPServerDisconnected)):
        return True
    if isinstance(exc, OSError) and not isinstance(exc, smtplib.SMTPException):
        return True
    return False


def _is_transient(channel: str, exc: Exception) -> bool:
    if channel == "Resend":
        return _resend_error_is_transient(exc)
    if channel == "SMTP":
        return _smtp_error_is_transient(exc)
    return False


class EmailService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def send_notifications_sync(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> tuple[bool, bool]:
        """Синхронная отправка обоих писем (BackgroundTasks / ARQ worker)."""
        owner_msg = self._build_owner_email(request, analysis)
        user_msg = self._build_user_email(request, analysis)

        if not self.settings.email_configured:
            logger.warning("Email not configured — messages logged instead of sent")
            self._log_email("OWNER", owner_msg)
            self._log_email("USER", user_msg)
            return False, False

        owner_sent = self._deliver(owner_msg)
        user_sent = self._deliver(user_msg)
        return owner_sent, user_sent

    def send_owner_notification(
        self,
        request: ContactRequest,
        analysis: AIAnalysis,
        *,
        idempotency_key: str | None = None,
    ) -> bool:
        """Письмо владельцу. Уже доставленное письмо сюда не передают повторно."""
        return self._send_labeled(
            "OWNER", self._build_owner_email(request, analysis), idempotency_key
        )

    def send_user_notification(
        self,
        request: ContactRequest,
        analysis: AIAnalysis,
        *,
        idempotency_key: str | None = None,
    ) -> bool:
        """Письмо клиенту. Уже доставленное письмо сюда не передают повторно."""
        return self._send_labeled(
            "USER", self._build_user_email(request, analysis), idempotency_key
        )

    def _send_labeled(
        self, kind: str, msg: EmailMessage, idempotency_key: str | None = None
    ) -> bool:
        if not self.settings.email_configured:
            logger.warning("Email not configured — messages logged instead of sent")
            self._log_email(kind, msg)
            return False
        return self._deliver(msg, idempotency_key)

    def _deliver(self, msg: EmailMessage, idempotency_key: str | None = None) -> bool:
        # Один ключ на все попытки этого письма. Без id обращения — случайный,
        # чтобы одинаковые тексты разных заявок не схлопывались в Resend.
        resend_key = idempotency_key or uuid.uuid4().hex
        if self.settings.resend_configured:
            if self._attempt_channel(
                "Resend",
                msg,
                lambda message: self._send_resend_once(message, resend_key),
            ):
                return True
            if not self.settings.smtp_configured:
                self._log_email("FALLBACK", msg)
                return False
            logger.warning("Resend failed for %s, falling back to SMTP", msg["To"])
        if self.settings.smtp_configured:
            if self._attempt_channel("SMTP", msg, self._send_smtp_once):
                return True
            self._log_email("FALLBACK", msg)
            return False
        self._log_email("FALLBACK", msg)
        return False

    def _attempt_channel(self, channel: str, msg: EmailMessage, send_once) -> bool:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_DELIVERY_ATTEMPTS + 1):
            try:
                send_once(msg)
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_DELIVERY_ATTEMPTS and _is_transient(channel, exc):
                    delay = RETRY_BACKOFF_SECONDS[
                        min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)
                    ]
                    logger.warning(
                        "Transient %s failure for %s (attempt %s/%s), retrying in %ss: %s",
                        channel,
                        msg["To"],
                        attempt,
                        MAX_DELIVERY_ATTEMPTS,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                    continue
                logger.error(
                    "Failed to send email via %s to %s: %s", channel, msg["To"], exc
                )
                return False
            logger.info("Email sent via %s to %s", channel, msg["To"])
            return True
        logger.error("Failed to send email via %s to %s: %s", channel, msg["To"], last_exc)
        return False

    def _send_resend_once(self, msg: EmailMessage, idempotency_key: str) -> None:
        plain, html_body = self._extract_bodies(msg)
        payload: dict = {
            "from": str(msg["From"]),
            "to": [str(msg["To"])],
            "subject": str(msg["Subject"]),
            "text": plain,
        }
        if html_body:
            payload["html"] = html_body
        with httpx.Client(timeout=RESEND_TIMEOUT_SECONDS) as client:
            response = client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
                json=payload,
            )
            response.raise_for_status()

    def _send_smtp_once(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as server:
            if self.settings.smtp_use_tls:
                server.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                server.login(self.settings.smtp_username, self.settings.smtp_password)
            server.send_message(msg)

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
