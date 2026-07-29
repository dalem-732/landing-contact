"""Plain-text and HTML bodies for contact notification emails."""
from __future__ import annotations

import html

from app.schemas.contact import AIAnalysis, ContactRequest


def _esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def owner_plain(request: ContactRequest, analysis: AIAnalysis) -> str:
    return (
        "Новое обращение с формы обратной связи.\n\n"
        f"Имя: {request.name}\n"
        f"Email: {request.email}\n"
        f"Телефон: {request.phone}\n"
        f"Комментарий:\n{request.comment}\n\n"
        "── AI-анализ ──\n"
        f"Тональность: {analysis.sentiment.value}\n"
        f"Категория: {analysis.category.value}\n"
        f"Резюме: {analysis.summary}\n"
        f"Черновик ответа:\n{analysis.auto_reply}\n\n"
        f"(AI использован: {'да' if analysis.ai_used else 'нет, fallback'})"
    )


def owner_html(request: ContactRequest, analysis: AIAnalysis) -> str:
    ai_label = "да" if analysis.ai_used else "нет, fallback"
    return f"""\
<!DOCTYPE html>
<html lang="ru">
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#18181b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f5;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
        <tr><td style="padding:20px 24px;background:#18181b;color:#fafafa;font-size:18px;font-weight:bold;">
          Новое обращение: {_esc(analysis.category.value)}
        </td></tr>
        <tr><td style="padding:24px;">
          <p style="margin:0 0 12px;font-size:15px;line-height:1.5;">Новое обращение с формы обратной связи.</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font-size:14px;line-height:1.6;">
            <tr><td style="padding:4px 0;color:#71717a;width:110px;">Имя</td><td>{_esc(request.name)}</td></tr>
            <tr><td style="padding:4px 0;color:#71717a;">Email</td><td>{_esc(str(request.email))}</td></tr>
            <tr><td style="padding:4px 0;color:#71717a;">Телефон</td><td>{_esc(request.phone)}</td></tr>
          </table>
          <p style="margin:16px 0 6px;font-size:13px;color:#71717a;text-transform:uppercase;letter-spacing:0.04em;">Комментарий</p>
          <p style="margin:0;padding:12px;background:#f4f4f5;border-radius:6px;font-size:14px;line-height:1.5;white-space:pre-wrap;">{_esc(request.comment)}</p>
          <p style="margin:20px 0 6px;font-size:13px;color:#71717a;text-transform:uppercase;letter-spacing:0.04em;">AI-анализ</p>
          <p style="margin:0 0 8px;font-size:14px;line-height:1.5;">
            Тональность: <strong>{_esc(analysis.sentiment.value)}</strong><br>
            Категория: <strong>{_esc(analysis.category.value)}</strong><br>
            Резюме: {_esc(analysis.summary)}
          </p>
          <p style="margin:12px 0 6px;font-size:13px;color:#71717a;">Черновик ответа</p>
          <p style="margin:0;padding:12px;background:#ecfdf5;border-radius:6px;font-size:14px;line-height:1.5;white-space:pre-wrap;">{_esc(analysis.auto_reply)}</p>
          <p style="margin:16px 0 0;font-size:12px;color:#a1a1aa;">AI использован: {_esc(ai_label)}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def user_plain(request: ContactRequest, analysis: AIAnalysis) -> str:
    return (
        f"{analysis.auto_reply}\n\n"
        "── Копия вашего обращения ──\n"
        f"Имя: {request.name}\n"
        f"Телефон: {request.phone}\n"
        f"Сообщение: {request.comment}\n\n"
        "Это автоматическое уведомление, отвечать на него не нужно."
    )


def user_html(request: ContactRequest, analysis: AIAnalysis) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="ru">
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#18181b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f4f5;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
        <tr><td style="padding:20px 24px;background:#18181b;color:#fafafa;font-size:18px;font-weight:bold;">
          Обращение принято
        </td></tr>
        <tr><td style="padding:24px;">
          <p style="margin:0 0 16px;font-size:15px;line-height:1.6;white-space:pre-wrap;">{_esc(analysis.auto_reply)}</p>
          <p style="margin:0 0 8px;font-size:13px;color:#71717a;text-transform:uppercase;letter-spacing:0.04em;">Копия вашего обращения</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font-size:14px;line-height:1.6;">
            <tr><td style="padding:4px 0;color:#71717a;width:110px;">Имя</td><td>{_esc(request.name)}</td></tr>
            <tr><td style="padding:4px 0;color:#71717a;">Телефон</td><td>{_esc(request.phone)}</td></tr>
          </table>
          <p style="margin:12px 0 0;padding:12px;background:#f4f4f5;border-radius:6px;font-size:14px;line-height:1.5;white-space:pre-wrap;">{_esc(request.comment)}</p>
          <p style="margin:20px 0 0;font-size:12px;color:#a1a1aa;">Это автоматическое уведомление, отвечать на него не нужно.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
