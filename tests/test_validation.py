"""Тесты валидации входных данных формы."""
import pytest
from pydantic import ValidationError

from app.schemas.contact import ContactRequest


def test_valid_request():
    req = ContactRequest(
        name="Иван Петров",
        email="ivan@example.com",
        phone="+7 999 123-45-67",
        comment="Здравствуйте! Хочу обсудить проект.",
    )
    assert req.phone.startswith("+7")
    assert req.email == "ivan@example.com"


def test_invalid_email():
    with pytest.raises(ValidationError):
        ContactRequest(name="Иван", email="not-an-email",
                       phone="+7 999 123-45-67", comment="Привет мир")


def test_invalid_phone():
    with pytest.raises(ValidationError):
        ContactRequest(name="Иван", email="ivan@example.com",
                       phone="123", comment="Привет мир")


def test_short_name():
    with pytest.raises(ValidationError):
        ContactRequest(name="A", email="ivan@example.com",
                       phone="+7 999 123-45-67", comment="Привет мир")


def test_comment_strips_controls_but_keeps_tags():
    req = ContactRequest(
        name="Иван", email="ivan@example.com", phone="+7 999 123-45-67",
        comment="<script>alert('x')</script> обычный текст" + chr(7),
    )
    assert "<script>" in req.comment
    assert "&lt;script&gt;" not in req.comment
    assert chr(7) not in req.comment
    assert "обычный текст" in req.comment
