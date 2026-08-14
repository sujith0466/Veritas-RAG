import pytest
from unittest.mock import AsyncMock, patch

from backend.core.config.smtp import SmtpSettings
from backend.services.email.provider import SMTPEmailProvider

@pytest.fixture
def mock_settings():
    with patch("backend.services.email.provider.get_settings") as mock_get:
        # Provide valid config to test sending logic
        settings = mock_get.return_value
        settings.smtp = SmtpSettings(
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=587,
            SMTP_USER="user",
            SMTP_PASSWORD="password",
            SMTP_FROM_EMAIL="noreply@example.com",
            SMTP_TLS_MODE="starttls",
            SMTP_TIMEOUT=5.0
        )
        yield mock_get

@pytest.fixture
def mock_unconfigured_settings():
    with patch("backend.services.email.provider.get_settings") as mock_get:
        settings = mock_get.return_value
        settings.smtp = SmtpSettings(
            SMTP_HOST="",
            SMTP_PORT=587
        )
        yield mock_get

@pytest.mark.asyncio
async def test_unconfigured_smtp_aborts_send(mock_unconfigured_settings):
    provider = SMTPEmailProvider()
    result = await provider._send_email("test@example.com", "Subject", "Body")
    assert result is False

@pytest.mark.asyncio
@patch("aiosmtplib.SMTP")
async def test_successful_email_dispatch(mock_smtp_class, mock_settings):
    mock_smtp_instance = AsyncMock()
    # aiosmtplib.SMTP acts as an async context manager
    mock_smtp_class.return_value.__aenter__.return_value = mock_smtp_instance
    
    provider = SMTPEmailProvider()
    result = await provider.send_verification_email("test@example.com", "token123")
    
    assert result is True
    mock_smtp_instance.login.assert_awaited_once_with("user", "password")
    mock_smtp_instance.send_message.assert_awaited_once()

@pytest.mark.asyncio
@patch("aiosmtplib.SMTP")
async def test_email_dispatch_exception_is_swallowed_safely(mock_smtp_class, mock_settings):
    mock_smtp_instance = AsyncMock()
    mock_smtp_class.return_value.__aenter__.return_value = mock_smtp_instance
    mock_smtp_instance.send_message.side_effect = Exception("Connection Timeout")
    
    provider = SMTPEmailProvider()
    result = await provider.send_password_reset_email("test@example.com", "token123")
    
    # Should swallow exception and return False so auth flows don't crash
    assert result is False

@pytest.mark.asyncio
@patch("aiosmtplib.SMTP")
async def test_send_invitation_email_formats_correctly(mock_smtp_class, mock_settings):
    mock_smtp_instance = AsyncMock()
    mock_smtp_class.return_value.__aenter__.return_value = mock_smtp_instance
    
    provider = SMTPEmailProvider()
    result = await provider.send_invitation_email(
        "newuser@example.com",
        "inviteToken123",
        "Test Workspace",
        "member"
    )
    
    assert result is True
    mock_smtp_instance.send_message.assert_awaited_once()
    sent_message = mock_smtp_instance.send_message.await_args[0][0]
    
    assert sent_message["To"] == "newuser@example.com"
    assert sent_message["From"] == "noreply@example.com"
    assert "invited to join Test Workspace" in sent_message["Subject"]
    assert "inviteToken123" in sent_message.get_content()
