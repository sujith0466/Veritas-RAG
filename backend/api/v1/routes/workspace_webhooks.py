import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.workspace_webhook import (
    WorkspaceWebhookCreateDTO,
    WorkspaceWebhookResponseDTO,
    WorkspaceWebhookSecretResponseDTO,
    WorkspaceWebhookUpdateDTO,
    WebhookDeliveryLogsResponseDTO,
    WebhookDeliveryLogDTO,
    WebhookEventCategoryDTO,
    WebhookTestDispatchResponseDTO,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.workspace import require_workspace_admin_or_owner
from backend.core.events.types import EventType
from backend.services.workspace_webhooks import (
    WebhookNotFoundException,
    WebhookValidationException,
    WorkspaceWebhookService,
)
from backend.tasks.webhooks import deliver_webhook_event_task

router = APIRouter(prefix="/workspaces/{tenant_id}/webhooks", tags=["workspace-webhooks"])


@router.get("/events", response_model=List[WebhookEventCategoryDTO])
async def list_webhook_events(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """List all available canonical webhook event categories and topics."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)

    # Categorize canonical domain events
    categories: dict[str, list[dict[str, str]]] = {
        "Document Intelligence": [],
        "Workspace & Members": [],
        "Reliability & Drift": [],
        "Security & Audit": [],
        "System & Operations": [],
    }

    for ev in EventType:
        val = ev.value
        name = ev.name.replace("_", " ").title()
        item = {"id": val, "name": name}
        if "document" in val or "chunk" in val or "vector" in val or "folder" in val:
            categories["Document Intelligence"].append(item)
        elif "workspace" in val or "member" in val or "invitation" in val:
            categories["Workspace & Members"].append(item)
        elif "reliability" in val or "drift" in val or "score" in val or "alert" in val or "confidence" in val:
            categories["Reliability & Drift"].append(item)
        elif "user" in val or "auth" in val or "security" in val or "audit" in val:
            categories["Security & Audit"].append(item)
        else:
            categories["System & Operations"].append(item)

    return [{"category": k, "events": v} for k, v in categories.items()]


@router.get("", response_model=List[WorkspaceWebhookResponseDTO])
async def list_webhooks(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """List all webhooks for a workspace."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)
    service = WorkspaceWebhookService(db)
    webhooks = await service.get_webhooks(tenant_id)
    return webhooks


@router.post("", response_model=WorkspaceWebhookSecretResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    tenant_id: uuid.UUID,
    data: WorkspaceWebhookCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Create a new webhook and return the raw secret (one-time display)."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)
    service = WorkspaceWebhookService(db)
    try:
        webhook, raw_secret = await service.create_webhook(tenant_id, data)
        return {"id": webhook.id, "secret": raw_secret}
    except WebhookValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{webhook_id}", response_model=WorkspaceWebhookResponseDTO)
async def update_webhook(
    tenant_id: uuid.UUID,
    webhook_id: uuid.UUID,
    data: WorkspaceWebhookUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Update an existing webhook configuration."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)
    service = WorkspaceWebhookService(db)
    try:
        webhook = await service.update_webhook(tenant_id, webhook_id, data)
        return webhook
    except WebhookNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    except WebhookValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    tenant_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Delete a webhook configuration."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)
    service = WorkspaceWebhookService(db)
    try:
        await service.delete_webhook(tenant_id, webhook_id)
    except WebhookNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")


@router.get("/logs", response_model=WebhookDeliveryLogsResponseDTO)
async def get_webhook_delivery_logs(
    tenant_id: uuid.UUID,
    webhook_id: Optional[uuid.UUID] = Query(None, description="Filter logs for a specific webhook ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Retrieve paginated delivery logs for this workspace."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)
    service = WorkspaceWebhookService(db)
    try:
        logs, total = await service.get_delivery_logs(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            limit=limit,
            offset=offset
        )
    except WebhookNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    items = []
    for l in logs:
        snapshot = l.payload_snapshot or {}
        event_name = snapshot.get("event", "unknown")
        # Mask and return only safe payload summary without sensitive credentials
        raw_payload = snapshot.get("payload", {})
        summary = {
            "keys": list(raw_payload.keys()) if isinstance(raw_payload, dict) else [],
            "tenant_id": str(tenant_id),
        }
        items.append(
            WebhookDeliveryLogDTO(
                id=l.id,
                target=l.target,
                status=l.status,
                attempt_count=l.attempt_count,
                error_message=l.error_message,
                created_at=l.created_at,
                event_type=event_name,
                payload_summary=summary,
            )
        )

    return WebhookDeliveryLogsResponseDTO(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/{webhook_id}/test", response_model=WebhookTestDispatchResponseDTO)
async def test_webhook_dispatch(
    tenant_id: uuid.UUID,
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(get_current_user),
):
    """Dispatches an authentic test.ping event to the webhook endpoint."""
    await require_workspace_admin_or_owner(tenant_id, current_user, db)
    service = WorkspaceWebhookService(db)
    webhook = await service.get_webhook_by_id(tenant_id, webhook_id)

    test_event_type = "test.ping"
    test_payload = {
        "event": test_event_type,
        "webhook_id": str(webhook.id),
        "tenant_id": str(tenant_id),
        "triggered_by": current_user.email,
        "message": "Veritas-RAG secure webhook test delivery",
    }

    # Asynchronously dispatch via the verified secure Celery delivery task
    deliver_webhook_event_task.delay(
        tenant_id_str=str(tenant_id),
        event_type=test_event_type,
        payload=test_payload
    )

    return WebhookTestDispatchResponseDTO(
        status="QUEUED",
        message="Test event dispatched to webhook delivery worker.",
        event=test_event_type
    )
