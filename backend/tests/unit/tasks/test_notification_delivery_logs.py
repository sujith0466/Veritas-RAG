"""Unit tests for NotificationDeliveryLog ORM and task logging compatibility.

Covers CHAT-001 remediation.
"""

from datetime import UTC, datetime
import uuid
import pytest
from sqlalchemy import select

from backend.database.engine import get_session_factory
from backend.models.entities.notification_delivery_log import NotificationDeliveryLog


@pytest.mark.asyncio
async def test_notification_delivery_log_orm_insert():
    """Test creating and persisting NotificationDeliveryLog with modern schema fields."""
    tenant_id = uuid.uuid4()
    target = "test-recipient@example.com"
    payload = {"subject": "Test Notification Subject", "event": "DOCUMENT_INDEXED"}

    factory = get_session_factory()
    async with factory() as session:
        log = NotificationDeliveryLog(
            tenant_id=tenant_id,
            type="EMAIL",
            target=target,
            payload_snapshot=payload,
            status="PENDING",
            attempt_count=1,
            next_retry_at=datetime.now(UTC),
            error_message=None,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.id is not None
        assert str(log.tenant_id) == str(tenant_id)
        assert log.type == "EMAIL"
        assert log.target == target
        assert log.payload_snapshot == payload
        assert log.status == "PENDING"
        assert log.attempt_count == 1
        assert log.is_deleted is False

        # Query back from DB
        stmt = select(NotificationDeliveryLog).where(NotificationDeliveryLog.id == log.id)
        result = await session.execute(stmt)
        fetched = result.scalar_one()

        assert fetched.id == log.id
        assert fetched.payload_snapshot["subject"] == "Test Notification Subject"
        assert fetched.attempt_count == 1

        # Clean up test row
        await session.delete(fetched)
        await session.commit()


@pytest.mark.asyncio
async def test_notification_delivery_log_webhook_orm_insert():
    """Test creating and persisting Webhook NotificationDeliveryLog with modern schema fields."""
    tenant_id = uuid.uuid4()
    target = "https://webhook.example.com/events"
    payload = {"event": "DOCUMENT_PROCESSED", "payload": {"doc_id": str(uuid.uuid4())}}

    factory = get_session_factory()
    async with factory() as session:
        log = NotificationDeliveryLog(
            tenant_id=tenant_id,
            type="WEBHOOK",
            target=target,
            payload_snapshot=payload,
            status="PENDING",
            attempt_count=1,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        assert log.id is not None
        assert log.payload_snapshot["event"] == "DOCUMENT_PROCESSED"
        assert log.attempt_count == 1

        # Clean up test row
        await session.delete(log)
        await session.commit()
