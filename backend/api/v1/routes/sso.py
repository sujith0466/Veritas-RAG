"""SSO Configuration API Routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.sso import (
    IdentityProviderCreateRequest,
    IdentityProviderResponse,
)
from backend.core.dependencies.database import get_db
from backend.core.events import EventDispatcher, get_dispatcher
from backend.services.sso_service import SSOService, SSOServiceError

router = APIRouter(prefix="/workspaces/{workspace_slug}/idp", tags=["Workspace SSO"])

@router.post(
    "",
    response_model=IdentityProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Identity Provider Configuration",
    description="Configures SAML/OIDC for a workspace. RBAC required: WORKSPACE_OWNER.",
)
async def create_idp(
    workspace_slug: str,
    payload: IdentityProviderCreateRequest,
    session: AsyncSession = Depends(get_db),
    dispatcher: EventDispatcher = Depends(get_dispatcher),
) -> dict:
    service = SSOService(session, dispatcher)
    # Stub: Retrieve workspace_id from slug
    workspace_id = uuid.uuid4()
    try:
        idp = await service.create_idp(workspace_id, payload.model_dump())
    except SSOServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "id": idp.id,
        "workspace_id": idp.workspace_id,
        "name": idp.name,
        "type": idp.type,
        "is_active": idp.is_active,
        "entity_id_issuer": idp.entity_id_issuer,
        "sso_url": idp.sso_url,
        "logout_url": idp.logout_url,
        "metadata_url": idp.metadata_url,
        "certificates": idp.certificates,
        "attribute_mapping": idp.attribute_mapping,
        "domain_restrictions": idp.domain_restrictions,
        "jit_enabled": idp.jit_enabled,
        "force_sso": idp.force_sso,
        "created_at": idp.created_at,
        "updated_at": idp.updated_at,
    }

@router.get(
    "",
    response_model=list[IdentityProviderResponse],
    summary="List all Identity Providers for a workspace"
)
async def list_idps(
    workspace_slug: str,
    session: AsyncSession = Depends(get_db),
) -> list[IdentityProviderResponse]:
    from sqlalchemy import select

    from backend.models.entities.identity_provider import IdentityProvider
    stmt = select(IdentityProvider)
    result = await session.execute(stmt)
    return list(result.scalars().all())
