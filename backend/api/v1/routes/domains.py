"""Domain Verification API Routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.domains import (
    DomainCreateRequest,
    DomainCreateResponse,
    DomainResponse,
)
from backend.core.dependencies.database import get_db
from backend.core.events import EventDispatcher, get_dispatcher
from backend.services.domain_service import (
    DomainAlreadyVerifiedError,
    DomainCooldownError,
    DomainServiceError,
    WorkspaceDomainService,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/domains", tags=["Workspace Domains"])


@router.post(
    "",
    response_model=DomainCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new domain for verification",
    description="Adds a domain and returns a verification token. RBAC required: WORKSPACE_OWNER or WORKSPACE_ADMIN.",
)
async def add_domain(
    workspace_id: uuid.UUID,
    payload: DomainCreateRequest,
    session: AsyncSession = Depends(get_db),
    dispatcher: EventDispatcher = Depends(get_dispatcher),
) -> dict:
    service = WorkspaceDomainService(session, dispatcher)
    try:
        domain, token = await service.add_domain(workspace_id, payload.domain_name)
    except DomainCooldownError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except DomainAlreadyVerifiedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DomainServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "id": domain.id,
        "workspace_id": domain.workspace_id,
        "domain_name": domain.domain_name,
        "status": domain.status,
        "is_primary": domain.is_primary,
        "last_verified_at": domain.last_verified_at,
        "token_expires_at": domain.token_expires_at,
        "dns_last_checked_at": domain.dns_last_checked_at,
        "error_reason": domain.error_reason,
        "created_at": domain.created_at,
        "updated_at": domain.updated_at,
        "verification_token": token,
    }

@router.post(
    "/{domain_id}/verify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger DNS TXT verification",
    description="Enqueues a Celery task to verify the domain via DNS. RBAC required: WORKSPACE_OWNER or WORKSPACE_ADMIN.",
)
async def verify_domain(
    workspace_id: uuid.UUID,
    domain_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    dispatcher: EventDispatcher = Depends(get_dispatcher),
) -> None:
    service = WorkspaceDomainService(session, dispatcher)
    try:
        await service.trigger_verification(domain_id)
    except DomainServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get(
    "",
    response_model=list[DomainResponse],
    summary="List all domains for a workspace"
)
async def list_domains(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DomainResponse]:
    from sqlalchemy import select

    from backend.models.entities.workspace_domain import WorkspaceDomain
    stmt = select(WorkspaceDomain).where(WorkspaceDomain.workspace_id == workspace_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())
