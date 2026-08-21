import pytest
import uuid
import ipaddress
from unittest.mock import patch, MagicMock

from backend.services.workspace_webhooks import WorkspaceWebhookService, WebhookValidationException
from backend.api.v1.schemas.workspace_webhook import WorkspaceWebhookCreateDTO

@pytest.fixture
def mock_session():
    session = MagicMock()
    return session

@pytest.mark.asyncio
async def test_webhook_url_validation_success(mock_session):
    service = WorkspaceWebhookService(mock_session)

    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        # Mock resolving to a public IP (e.g. 8.8.8.8)
        mock_getaddrinfo.return_value = [
            (2, 1, 6, '', ('8.8.8.8', 443))
        ]

        # Should not raise
        await service._resolve_and_validate_url("https://example.com/webhook")

@pytest.mark.asyncio
async def test_webhook_url_validation_fails_http(mock_session):
    service = WorkspaceWebhookService(mock_session)

    with pytest.raises(WebhookValidationException, match="Webhook URL must use HTTPS"):
        await service._resolve_and_validate_url("http://example.com/webhook")

@pytest.mark.asyncio
async def test_webhook_url_validation_fails_private_ip(mock_session):
    service = WorkspaceWebhookService(mock_session)

    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        # Mock resolving to a private IP
        mock_getaddrinfo.return_value = [
            (2, 1, 6, '', ('10.0.0.1', 443))
        ]

        with pytest.raises(WebhookValidationException, match="protected or private range"):
            await service._resolve_and_validate_url("https://internal.example.com/webhook")

@pytest.mark.asyncio
async def test_webhook_url_validation_fails_metadata(mock_session):
    service = WorkspaceWebhookService(mock_session)

    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [
            (2, 1, 6, '', ('169.254.169.254', 443))
        ]

        with pytest.raises(WebhookValidationException, match="Cloud metadata endpoint access is strictly prohibited"):
            await service._resolve_and_validate_url("https://metadata.example.com/webhook")

@pytest.mark.asyncio
async def test_webhook_url_validation_fails_localhost(mock_session):
    service = WorkspaceWebhookService(mock_session)

    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [
            (2, 1, 6, '', ('127.0.0.1', 443))
        ]

        with pytest.raises(WebhookValidationException, match="protected or private range"):
            await service._resolve_and_validate_url("https://localhost/webhook")
