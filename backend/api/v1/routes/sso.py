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

from backend.core.auth.context import UserContext
from backend.core.dependencies.rbac import require_role
from backend.core.permissions.rbac import Role
from backend.repositories.workspace import WorkspaceRepository

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
    user_context: UserContext = Depends(require_role(Role.OWNER)),
) -> dict:
    repo = WorkspaceRepository(session)
    workspace = await repo.get_by_slug(workspace_slug)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if str(user_context.tenant_id) != str(workspace.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace membership")

    service = SSOService(session, dispatcher)
    workspace_id = workspace.id
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
