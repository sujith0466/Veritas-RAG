"""Tests for Workspace Webhooks API and Service."""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from backend.api.v1.schemas.workspace_webhook import WorkspaceWebhookCreateDTO
from backend.services.workspace_webhooks import (
    WorkspaceWebhookService,
    WebhookValidationException,
    WebhookNotFoundException,
)
from backend.models.entities.workspace_webhook import WorkspaceWebhook
from backend.core.events.types import EventType


@pytest.mark.asyncio
async def test_validate_events_canonical():
    session = AsyncMock()
    service = WorkspaceWebhookService(session)

    # Valid canonical events
    service._validate_events(["*"])
    service._validate_events([EventType.DOCUMENT_UPLOADED.value, EventType.WORKSPACE_ARCHIVED.value])

    # Invalid event
    with pytest.raises(WebhookValidationException):
        service._validate_events(["invalid.made_up.event"])


@pytest.mark.asyncio
async def test_get_delivery_secret_legacy_and_encrypted():
    session = AsyncMock()
    service = WorkspaceWebhookService(session)

    # 1. Plaintext legacy fallback
    legacy_wh = WorkspaceWebhook(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        endpoint_url="https://example.com/webhook",
        secret_hash="whsec_plain_legacy_secret",
        encrypted_secret=None,
        events=["*"],
        is_active=True,
    )
    secret = await service.get_delivery_secret(legacy_wh)
    assert secret == "whsec_plain_legacy_secret"
    # Transparent upgrade initiated
    assert legacy_wh.encrypted_secret is not None
    assert legacy_wh.encrypted_secret.startswith("v1:")

    # 2. Already encrypted
    secret2 = await service.get_delivery_secret(legacy_wh)
    assert secret2 == "whsec_plain_legacy_secret"


@pytest.mark.asyncio
async def test_migrate_legacy_webhook_secrets():
    session = AsyncMock()
    service = WorkspaceWebhookService(session)

    # Mock unencrypted legacy webhook and already-encrypted webhook
    wh_legacy = WorkspaceWebhook(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        endpoint_url="https://example.com/legacy",
        secret_hash="whsec_dormant_unencrypted_secret",
        encrypted_secret=None,
        events=["*"],
        is_active=True,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [wh_legacy]
    session.execute.return_value = mock_result

    summary = await service.migrate_legacy_webhook_secrets(batch_size=10)
    assert summary["inspected"] == 1
    assert summary["migrated"] == 1
    assert summary["failed"] == 0

    assert wh_legacy.encrypted_secret is not None
    assert wh_legacy.encrypted_secret.startswith("v1:")
    session.commit.assert_awaited_once()

