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
    from backend.services.email.provider import EmailConfigurationError
    provider = SMTPEmailProvider()
    with pytest.raises(EmailConfigurationError):
        await provider._send_email("test@example.com", "Subject", "Body")

@pytest.mark.asyncio
@patch("backend.tasks.emails.send_email_task.delay")
async def test_successful_email_dispatch(mock_delay, mock_settings):
    provider = SMTPEmailProvider()
    result = await provider.send_verification_email("test@example.com", "token123")
    
    assert result is True
    mock_delay.assert_called_once()
    _, kwargs = mock_delay.call_args
    assert kwargs["to_addresses"] == ["test@example.com"]
    assert "token123" in kwargs["text_content"]

@pytest.mark.asyncio
@patch("backend.tasks.emails.send_email_task.delay")
async def test_email_dispatch_exception_is_swallowed_safely(mock_delay, mock_settings):
    mock_delay.side_effect = Exception("Connection Timeout")
    
    provider = SMTPEmailProvider()
    with pytest.raises(Exception, match="Connection Timeout"):
        await provider.send_password_reset_email("test@example.com", "token123")

@pytest.mark.asyncio
@patch("backend.tasks.emails.send_email_task.delay")
async def test_send_invitation_email_formats_correctly(mock_delay, mock_settings):
    mock_settings.return_value.frontend_url = "https://app.veritas-rag.internal"
    provider = SMTPEmailProvider()
    result = await provider.send_invitation_email(
        "newuser@example.com",
        "inviteToken123",
        "Test Workspace",
        "member"
    )
    
    assert result is True
    mock_delay.assert_called_once()
    _, kwargs = mock_delay.call_args
    
    assert kwargs["to_addresses"] == ["newuser@example.com"]
    assert "invited to join Test Workspace" in kwargs["subject"]
    assert "inviteToken123" in kwargs["text_content"]
    assert "https://app.veritas-rag.internal/invitations/accept?token=inviteToken123" in kwargs["text_content"]
