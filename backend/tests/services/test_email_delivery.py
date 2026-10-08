"""Automated tests for Celery email delivery and SMTP fail-closed resilience."""

import asyncio
from email.message import EmailMessage
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import uuid

import pytest

from backend.services.email.provider import (
    ConsoleEmailProvider,
    EmailConfigurationError,
    EmailProvider,
    MockEmailProvider,
    SMTPEmailProvider,
)
from backend.tasks.emails import _build_mime_message, _async_send_email, send_email_task


def test_mime_message_construction():
    """Verify MIME builder produces a valid RFC 2822 multipart/alternative message."""
    from_addr = "no-reply@raguard.io"
    to_addrs = ["alice@example.com"]
    subject = "Join Veritas Workspace"
    html_content = "<h1>Welcome to Veritas</h1><p>Click here to join</p>"
    text_content = "Welcome to Veritas. Visit link to join."

    msg = _build_mime_message(
        from_addr=from_addr,
        to_addrs=to_addrs,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )

    assert isinstance(msg, EmailMessage)
    assert msg["From"] == from_addr
    assert msg["To"] == "alice@example.com"
    assert msg["Subject"] == subject
    assert msg.is_multipart()

    parts = list(msg.iter_parts())
    assert len(parts) == 2
    content_types = [p.get_content_type() for p in parts]
    assert "text/plain" in content_types
    assert "text/html" in content_types

    # Verify non-empty body payload
    html_part = next(p for p in parts if p.get_content_type() == "text/html")
    assert "<h1>Welcome to Veritas</h1>" in html_part.get_content()


@pytest.mark.asyncio
async def test_smtp_provider_fail_closed_when_unconfigured():
    """Verify SMTPEmailProvider raises EmailConfigurationError when SMTP is not configured."""
    with patch("backend.services.email.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.smtp.is_configured = False
        mock_get_settings.return_value = mock_settings

        provider = SMTPEmailProvider()
        msg = EmailMessage()
        msg["From"] = "test@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Test"
        msg.set_content("Test body")

        with pytest.raises(EmailConfigurationError) as exc_info:
            await provider.send_message(msg)

        assert "SMTP settings are not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_send_email_marks_failed_permanent_on_config_error():
    """Verify _async_send_email marks notification log as FAILED_PERMANENT on EmailConfigurationError."""
    mock_log = MagicMock()
    mock_log.id = uuid.uuid4()
    mock_log.status = "PENDING"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_log)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    mock_task = MagicMock()
    mock_task.request.retries = 0
    mock_task.retry = MagicMock()

    with patch("backend.tasks.emails.get_session_factory", return_value=mock_factory), \
         patch("backend.tasks.emails.SMTPEmailProvider.send_message", side_effect=EmailConfigurationError("SMTP unconfigured")), \
         patch("backend.tasks.emails.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.smtp.from_email = "noreply@raguard.ai"
        mock_get_settings.return_value = mock_settings

        await _async_send_email(
            task=mock_task,
            tenant_id=uuid.uuid4(),
            subject="Test Notification",
            to_addresses=["user@example.com"],
            html_content="<p>Test</p>",
            text_content="Test",
        )

        assert mock_log.status == "FAILED_PERMANENT"
        assert "SMTP unconfigured" in mock_log.error_message
        mock_task.retry.assert_not_called()


@pytest.mark.asyncio
async def test_async_send_email_retries_transient_error():
    """Verify _async_send_email schedules retry and sets FAILED_TRANSIENT on network failure."""
    mock_log = MagicMock()
    mock_log.id = uuid.uuid4()
    mock_log.status = "PENDING"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_log)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    mock_task = MagicMock()
    mock_task.request.retries = 1
    mock_task.retry = MagicMock(side_effect=Exception("TaskRetried"))

    with patch("backend.tasks.emails.get_session_factory", return_value=mock_factory), \
         patch("backend.tasks.emails.SMTPEmailProvider.send_message", side_effect=ConnectionResetError("Connection lost")), \
         patch("backend.tasks.emails.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.smtp.from_email = "noreply@raguard.ai"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(Exception) as exc_info:
            await _async_send_email(
                task=mock_task,
                tenant_id=uuid.uuid4(),
                subject="Test Notification",
                to_addresses=["user@example.com"],
                html_content="<p>Test</p>",
                text_content="Test",
            )

        assert "TaskRetried" in str(exc_info.value)
        assert mock_log.status == "FAILED_TRANSIENT"
        mock_task.retry.assert_called_once()


@pytest.mark.asyncio
async def test_smtp_provider_builds_password_changed_notification():
    """Verify SMTPEmailProvider constructs and dispatches password changed notification."""
    provider = SMTPEmailProvider()
    to_email = "alice@example.com"
    event_time = datetime.datetime(2026, 10, 8, 14, 30, 0, tzinfo=datetime.UTC)
    ip_address = "192.0.2.42"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    with patch.object(provider, "_send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        result = await provider.send_password_changed_notification_email(
            to_email=to_email,
            event_time=event_time,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        assert result is True
        mock_send.assert_awaited_once()

        call_args = mock_send.await_args
        recipient = call_args.args[0]
        subject = call_args.args[1]
        text_body = call_args.args[2]
        html_body = call_args.kwargs.get("html_body")

        assert recipient == to_email
        assert subject == "Security Alert: Your Veritas-RAG Password Has Been Changed"
        assert "2026-10-08 14:30:00 UTC" in text_body
        assert "192.0.2.42" in text_body
        assert "Mozilla/5.0" in text_body
        assert "If you did NOT change your password" in text_body

        assert html_body is not None
        assert "Security Alert: Password Changed" in html_body
        assert "2026-10-08 14:30:00 UTC" in html_body
        assert "192.0.2.42" in html_body
        assert "Mozilla/5.0" in html_body


@pytest.mark.asyncio
async def test_password_changed_notification_payload_zero_secrets():
    """Verify password changed notification contains NO prohibited authentication secrets."""
    provider = SMTPEmailProvider()
    to_email = "bob@example.com"
    event_time = datetime.datetime.now(datetime.UTC)

    with patch.object(provider, "_send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        await provider.send_password_changed_notification_email(
            to_email=to_email,
            event_time=event_time,
            ip_address="10.0.0.1",
            user_agent="TestAgent/1.0",
        )

        call_args = mock_send.await_args
        text_body = call_args.args[2]
        html_body = call_args.kwargs.get("html_body", "")

        for prohibited in [
            "password_hash",
            "$2b$",
            "argon2",
            "pbkdf2",
            "eyJ",  # JWT header prefix
            "Bearer ",
            "otp_hash",
            "change_token",
            "reset_token",
            "session_id",
            "cookie",
            "redis",
        ]:
            assert prohibited.lower() not in text_body.lower(), f"Prohibited secret '{prohibited}' leaked in text_body"
            assert prohibited.lower() not in html_body.lower(), f"Prohibited secret '{prohibited}' leaked in html_body"


@pytest.mark.asyncio
async def test_mock_provider_records_password_changed_notification(tmp_path):
    """Verify MockEmailProvider records password changed notification without secrets."""
    mock_file = str(tmp_path / "mock_emails.json")
    provider = MockEmailProvider()
    provider.mock_file = mock_file

    to_email = "carol@example.com"
    event_time = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.UTC)

    result = await provider.send_password_changed_notification_email(
        to_email=to_email,
        event_time=event_time,
        ip_address="172.16.0.1",
        user_agent="BrowserMock/2.0",
    )

    assert result is True

    import json
    with open(mock_file, "r") as f:
        records = json.load(f)

    assert len(records) == 1
    record = records[0]
    assert record["type"] == "password_changed_notification"
    assert record["to"] == to_email
    assert record["token"] == ""  # Proves ZERO secret/token in record
    assert record["details"]["subject"] == "Security Alert: Your Veritas-RAG Password Has Been Changed"
    assert record["details"]["event_time"] == "2026-10-08 12:00:00 UTC"
    assert record["details"]["ip_address"] == "172.16.0.1"
    assert record["details"]["user_agent"] == "BrowserMock/2.0"


@pytest.mark.asyncio
async def test_console_provider_password_changed_notification():
    """Verify ConsoleEmailProvider handles password changed notification without error."""
    provider = ConsoleEmailProvider()
    result = await provider.send_password_changed_notification_email(
        to_email="dave@example.com",
        event_time=datetime.datetime.now(datetime.UTC),
    )
    assert result is True

