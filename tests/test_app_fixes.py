from __future__ import annotations

import pytest

from services.email_service import EmailService


def test_email_service_reports_missing_env(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SENDER_EMAIL", raising=False)
    monkeypatch.delenv("EMAIL_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("SENDER_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)

    service = EmailService()
    result = service._send("Subject", "<p>Body</p>", "patient@example.com")

    assert result["success"] is False
    assert result["reason"] == "smtp_not_configured"
    assert "EMAIL_USER" in result["missing_fields"]
    assert "EMAIL_PASSWORD" in result["missing_fields"]
    assert "Missing required setting" in result["error"]


def test_email_service_skips_placeholder_example_domain(monkeypatch):
    monkeypatch.setenv("EMAIL_USER", "sender@example.org")
    monkeypatch.setenv("EMAIL_PASSWORD", "app-password")

    service = EmailService()
    result = service._send("Subject", "<p>Body</p>", "patient@example.com")

    assert result["success"] is False
    assert result["skipped"] is True
    assert result["reason"] == "placeholder_recipient"


@pytest.mark.asyncio
async def test_favicon_redirect(client):
    response = await client.get("/favicon.ico", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/static/images/favicon.svg"
