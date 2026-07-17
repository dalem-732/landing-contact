"""Email-сервис: уведомление владельцу и копия пользователю."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIAnalysis, ContactRequest

logger = get_logger("app.email")


class EmailService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def send_notifications_sync(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> tuple[bool, bool]:
        """Синхронная отправка (вызывается из BackgroundTasks / ARQ worker)."""
        owner_msg = self._build_owner_email(request, analysis)
        user_msg = self._build_user_email(request, analysis)

        if not self.settings.smtp_configured:
            logger.warning("SMTP not configured — emails logged instead of sent")
            self._log_email("OWNER", owner_msg)
            self._log_email("USER", user_msg)
            return False, False

        owner_sent = self._send(owner_msg)
        user_sent = self._send(user_msg)
        return owner_sent, user_sent

    def _send(self, msg: EmailMessage) -> bool:
        try:
            with smtplib.SMTP(
                self.settings.smtp_host, self.settings.smtp_port, timeout=15
            ) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(msg)
            logger.info("Email sent to %s", msg["To"])
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", msg["To"], exc)
            self._log_email("FALLBACK", msg)
            return False

    def _build_owner_email(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"Новое обращение с лендинга: {analysis.category.value}"
        msg["From"] = self.settings.smtp_from
        msg["To"] = self.settings.owner_email
        msg.set_content(
            f"Новое обращение с формы обратной связи.\n\n"
            f"Имя: {request.name}\n"
            f"Email: {request.email}\n"
            f"Телефон: {request.phone}\n"
            f"Комментарий:\n{request.comment}\n\n"
            f"── AI-анализ ──\n"
            f"Тональность: {analysis.sentiment.value}\n"
            f"Категория: {analysis.category.value}\n"
            f"Резюме: {analysis.summary}\n"
            f"Черновик ответа:\n{analysis.auto_reply}\n\n"
            f"(AI использован: {'да' if analysis.ai_used else 'нет, fallback'})"
        )
        return msg

    def _build_user_email(
        self, request: ContactRequest, analysis: AIAnalysis
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = "Ваше обращение принято"
        msg["From"] = self.settings.smtp_from
        msg["To"] = request.email
        msg.set_content(
            f"{analysis.auto_reply}\n\n"
            f"── Копия вашего обращения ──\n"
            f"Имя: {request.name}\n"
            f"Телефон: {request.phone}\n"
            f"Сообщение: {request.comment}\n\n"
            f"Это автоматическое уведомление, отвечать на него не нужно."
        )
        return msg

    @staticmethod
    def _log_email(kind: str, msg: EmailMessage) -> None:
        logger.info(
            "[EMAIL:%s] to=%s subject=%s\n%s",
            kind, msg["To"], msg["Subject"], msg.get_content(),
        )


email_service = EmailService()
