"""Celery tasks for Webhook delivery."""

from celery import shared_task
from celery.utils.log import get_task_logger

import asyncio
import uuid
import datetime
import httpx
import hashlib
import hmac
import json
import time

from sqlalchemy import select

from backend.database.session import SessionLocal
from backend.models.entities.notification_delivery_log import NotificationDeliveryLog
from backend.models.entities.workspace_webhook import WorkspaceWebhook
from backend.services.workspace_webhooks import WorkspaceWebhookService
from backend.core.security.ssrf_transport import SSRFProtectedTransport, SSRFValidationError

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60, # 1 minute base backoff
    autoretry_for=(Exception,),
    queue="webhooks"
)
def deliver_webhook_event_task(self, tenant_id_str: str, event_type: str, payload: dict):
    """Delivers a webhook event to all subscribed active endpoints."""
    tenant_id = uuid.UUID(tenant_id_str)
    asyncio.run(_async_deliver_webhooks(self, tenant_id, event_type, payload))


async def _async_deliver_webhooks(task, tenant_id: uuid.UUID, event_type: str, payload: dict):
    async with SessionLocal() as session:
        # Find all active webhooks for this tenant subscribed to this event (or '*')
        stmt = select(WorkspaceWebhook).where(
            WorkspaceWebhook.tenant_id == tenant_id,
            WorkspaceWebhook.is_active == True,
            WorkspaceWebhook.is_deleted == False
        )
        result = await session.execute(stmt)
        webhooks = result.scalars().all()

    for webhook in webhooks:
        # Check event subscription: wildcard or exact event
        if "*" not in webhook.events and event_type not in webhook.events:
            continue

        await _deliver_to_endpoint(task, tenant_id, webhook, event_type, payload)


async def _deliver_to_endpoint(task, tenant_id: uuid.UUID, webhook: WorkspaceWebhook, event_type: str, payload: dict):
    logger.info(f"Delivering event {event_type} to webhook {webhook.id}")

    # Pre-record pending state
    async with SessionLocal() as session:
        log = NotificationDeliveryLog(
            tenant_id=str(tenant_id),
            type="WEBHOOK",
            target=webhook.endpoint_url,
            payload_snapshot={"event": event_type, "payload": payload},
            status="PENDING",
            attempt_count=task.request.retries + 1,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

    try:
        # SSRF Protection: Time-of-Use DNS Validation
        async with SessionLocal() as session:
            service = WorkspaceWebhookService(session)
            await service._resolve_and_validate_url(webhook.endpoint_url)
            # Decrypt secret with legacy fallback
            raw_secret = await service.get_delivery_secret(webhook)

        # Prepare Canonical Payload
        timestamp = str(int(time.time()))
        canonical_body = json.dumps(payload, separators=(',', ':'))

        # Generate HMAC-SHA256 signature using decrypted secret
        secret_bytes = raw_secret.encode('utf-8')
        signature = hmac.new(secret_bytes, canonical_body.encode('utf-8'), hashlib.sha256).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-RAGuard-Event": event_type,
            "X-RAGuard-Timestamp": timestamp,
            "X-RAGuard-Signature": f"sha256={signature}",
            "User-Agent": "Veritas-RAG-Webhook-Delivery/1.0"
        }

        # Defend against DNS rebinding and SSRF at connection time with IP pinning:
        # SSRFProtectedTransport preserves TLS SNI, certificate validation, and rejects private/prohibited IPs at connect_tcp.
        # follow_redirects=False prevents open-redirect SSRF bypasses.
        transport = SSRFProtectedTransport(verify=True)
        async with httpx.AsyncClient(transport=transport, timeout=10.0, follow_redirects=False) as client:
            response = await client.post(webhook.endpoint_url, content=canonical_body, headers=headers)
            response.raise_for_status()

        status = "SUCCESS"
        error_msg = None
    except SSRFValidationError as e:
        status = "FAILED_PERMANENT"
        error_msg = f"SSRF Protection Blocked Delivery: {e}"
    except httpx.HTTPStatusError as e:
        status = "FAILED_PERMANENT" if 400 <= e.response.status_code < 500 else "FAILED_TRANSIENT"
        error_msg = f"HTTP Error: {e.response.status_code}"
    except Exception as e:
        status = "FAILED_TRANSIENT"
        error_msg = str(e)

    # Update delivery log
    async with SessionLocal() as session:
        log_obj = await session.get(NotificationDeliveryLog, log.id)
        if log_obj:
            log_obj.status = status
            log_obj.error_message = error_msg
            if status == "FAILED_TRANSIENT":
                log_obj.next_retry_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=60 * (2 ** task.request.retries))
            await session.commit()

    if status == "FAILED_TRANSIENT":
        raise Exception(error_msg)
