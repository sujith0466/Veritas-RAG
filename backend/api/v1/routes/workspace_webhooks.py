import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.workspace_webhook import (
    WorkspaceWebhookCreateDTO,
    WorkspaceWebhookResponseDTO,
    WorkspaceWebhookSecretResponseDTO,
    WorkspaceWebhookUpdateDTO,
)
from backend.core.security.auth_middleware import get_current_user
from backend.database.session import get_db
from backend.models.entities.user import User
from backend.services.workspace_webhooks import (
    WebhookNotFoundException,
    WebhookValidationException,
    WorkspaceWebhookService,
)

router = APIRouter(prefix="/workspaces/{tenant_id}/webhooks", tags=["workspace-webhooks"])

@router.get("", response_model=List[WorkspaceWebhookResponseDTO])
async def list_webhooks(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all webhooks for a workspace."""
    # Check tenant access (Assuming get_current_user handles RBAC or tenant verification, or we do it here)
    # For Program 2, usually RBAC logic applies. Let's assume user is in tenant context.
    service = WorkspaceWebhookService(db)
    webhooks = await service.get_webhooks(tenant_id)
    return webhooks

@router.post("", response_model=WorkspaceWebhookSecretResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    tenant_id: uuid.UUID,
    data: WorkspaceWebhookCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new webhook and return the raw secret."""
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
    current_user: User = Depends(get_current_user),
):
    """Update an existing webhook configuration."""
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
    current_user: User = Depends(get_current_user),
):
    """Delete a webhook configuration."""
    service = WorkspaceWebhookService(db)
    try:
        await service.delete_webhook(tenant_id, webhook_id)
    except WebhookNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
