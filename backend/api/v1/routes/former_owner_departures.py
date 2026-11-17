"""FastAPI routes for Workspace Former Owner Departures.

Governed by Section 7 Batch 3 (WP 7.10, PO-D32-03).
Mounted under /api/v1/workspaces/{workspace_id}/former-owners/departures and transfers.
"""

from collections.abc import Sequence
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.former_owner_departure import (
    FormerOwnerDepartureResponse,
    FormerOwnerDepartureUserDTO,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.models.entities.workspace_former_owner_departure import WorkspaceFormerOwnerDeparture
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace_former_owner_departure import (
    WorkspaceFormerOwnerDepartureRepository,
)
from backend.services.workspace.former_owner_departure_service import (
    FormerOwnerDepartureService,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["Workspace Former Owner Departures"],
)


def _to_departure_dto(departure: WorkspaceFormerOwnerDeparture) -> FormerOwnerDepartureResponse:
    """Format SQLAlchemy entity into FormerOwnerDepartureResponse schema."""
    former_owner_dto = None
    if hasattr(departure, "former_owner") and departure.former_owner:
        former_owner_dto = FormerOwnerDepartureUserDTO(
            id=departure.former_owner.id,
            email=getattr(departure.former_owner, "email", None),
            full_name=getattr(departure.former_owner, "display_name", None)
            or getattr(departure.former_owner, "full_name", None),
        )

    confirmed_by_dto = None
    if hasattr(departure, "confirmed_by") and departure.confirmed_by:
        confirmed_by_dto = FormerOwnerDepartureUserDTO(
            id=departure.confirmed_by.id,
            email=getattr(departure.confirmed_by, "email", None),
            full_name=getattr(departure.confirmed_by, "display_name", None)
            or getattr(departure.confirmed_by, "full_name", None),
        )

    return FormerOwnerDepartureResponse(
        id=departure.id,
        workspace_id=departure.workspace_id,
        former_owner_id=departure.former_owner_id,
        transfer_id=departure.transfer_id,
        departure_type=departure.departure_type,
        former_role=departure.former_role,
        retained_role=departure.retained_role,
        departure_confirmed_at=departure.departure_confirmed_at,
        confirmed_by_user_id=departure.confirmed_by_user_id,
        departure_notes=departure.departure_notes,
        created_at=departure.created_at,
        former_owner=former_owner_dto,
        confirmed_by=confirmed_by_dto,
    )


@router.get(
    "/former-owners/departures",
    response_model=list[FormerOwnerDepartureResponse],
    status_code=status.HTTP_200_OK,
    summary="List former owner departures for a workspace",
)
async def list_workspace_former_owner_departures(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    limit: int = Query(50, ge=1, le=100, description="Max departures to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[FormerOwnerDepartureResponse]:
    """Retrieve historical departure records for former owners of the workspace."""
    departures = await FormerOwnerDepartureService.list_workspace_departures(
        session=session,
        workspace_id=workspace_id,
        caller_user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [_to_departure_dto(d) for d in departures]


@router.get(
    "/transfers/{transfer_id}/departure",
    response_model=FormerOwnerDepartureResponse,
    status_code=status.HTTP_200_OK,
    summary="Get former owner departure record for a specific transfer",
)
async def get_transfer_former_owner_departure(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    transfer_id: uuid.UUID = Path(..., description="The transfer ID"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> FormerOwnerDepartureResponse:
    """Retrieve departure record resulting from a completed ownership transfer."""
    # Verify caller is an active member
    mem_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == current_user.id,
        WorkspaceMember.status == MemberStatus.ACTIVE.value,
        WorkspaceMember.is_deleted == False,
    )
    member = (await session.execute(mem_stmt)).scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: user is not an active member of this workspace",
        )

    repo = WorkspaceFormerOwnerDepartureRepository(session)
    departure = await repo.get_by_transfer_id(transfer_id)
    if not departure or departure.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Former owner departure record not found for this transfer",
        )

    return _to_departure_dto(departure)
