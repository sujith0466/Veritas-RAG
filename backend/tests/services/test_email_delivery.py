"""Automated tests for Celery email delivery and SMTP fail-closed resilience."""

import asyncio
from email.message import EmailMessage
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.services.email.provider import (
    EmailConfigurationError,
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
