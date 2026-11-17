"""FastAPI routes for Workspace Ownership Transfers.

Governed by Section 7 Batch 1 (REV5).
Mounted under /api/v1/workspaces/{workspace_id}/transfers.
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Body, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.workspace_transfer import (
    FormerOwnerChoiceCreate,
    OwnershipNominationCreate,
    OwnershipRejectionCreate,
    OwnershipTransferResponse,
    OwnershipTransferUserDTO,
    RoleDecisionCreate,
)
from backend.api.v1.workspaces.dependencies import (
    require_active_workspace_member,
    require_active_workspace_owner,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace_ownership_transfer import (
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.services.workspace_transfer_service import WorkspaceTransferService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/transfers",
    tags=["Workspace Ownership Transfers"],
)


def _to_response_dto(transfer: WorkspaceOwnershipTransfer) -> OwnershipTransferResponse:
    """Format SQLAlchemy entity into OwnershipTransferResponse schema."""
    nom_user = None
    if hasattr(transfer, "nominated_by") and transfer.nominated_by:
        nom_user = OwnershipTransferUserDTO(
            id=transfer.nominated_by.id,
            email=transfer.nominated_by.email,
            full_name=getattr(transfer.nominated_by, "display_name", None) or getattr(transfer.nominated_by, "full_name", None),
        )

    nominee_user = None
    if hasattr(transfer, "nominee") and transfer.nominee:
        nominee_user = OwnershipTransferUserDTO(
            id=transfer.nominee.id,
            email=transfer.nominee.email,
            full_name=getattr(transfer.nominee, "display_name", None) or getattr(transfer.nominee, "full_name", None),
        )

    return OwnershipTransferResponse(
        id=transfer.id,
        workspace_id=transfer.workspace_id,
        nominated_by_user_id=transfer.nominated_by_user_id,
        nominee_user_id=transfer.nominee_user_id,
        status=transfer.status,
        rejection_reason=transfer.rejection_reason,
        created_at=transfer.created_at,
        expires_at=transfer.expires_at,
        responded_at=transfer.responded_at,
        cancelled_at=transfer.cancelled_at,
        expired_at=transfer.expired_at,
        is_expired=(transfer.status == TransferStatus.EXPIRED.value),
        former_owner_choice=getattr(transfer, "former_owner_choice", None) or "PENDING",
        former_owner_choice_at=getattr(transfer, "former_owner_choice_at", None),
        decision_status=getattr(transfer, "decision_status", None) or "PENDING",
        decision_deadline_at=getattr(transfer, "decision_deadline_at", None),
        decided_at=getattr(transfer, "decided_at", None),
        decided_by_user_id=getattr(transfer, "decided_by_user_id", None),
        response_notes=getattr(transfer, "response_notes", None),
        decision_notes=getattr(transfer, "decision_notes", None),
        current_owner_email_snapshot=getattr(transfer, "current_owner_email_snapshot", None),
        nominated_user_email_snapshot=getattr(transfer, "nominated_user_email_snapshot", None),
        nominated_by=nom_user,
        nominee=nominee_user,
    )


@router.post(
    "/nominate",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate workspace ownership nomination",
)
async def nominate_owner(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    payload: OwnershipNominationCreate = Body(...),
    owner_member: WorkspaceMember = Depends(require_active_workspace_owner),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OwnershipTransferResponse:
    service = WorkspaceTransferService()
    transfer = await service.initiate_nomination(
        session=session,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        nominee_user_id=payload.nominee_user_id,
    )
    return _to_response_dto(transfer)


@router.post(
    "/{transfer_id}/accept",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept workspace ownership nomination",
)
async def accept_transfer(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    transfer_id: uuid.UUID = Path(..., description="The transfer ID"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OwnershipTransferResponse:
    service = WorkspaceTransferService()
    transfer = await service.accept_transfer(
        session=session,
        workspace_id=workspace_id,
        transfer_id=transfer_id,
        current_user_id=current_user.id,
    )
    return _to_response_dto(transfer)


@router.post(
    "/{transfer_id}/reject",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject workspace ownership nomination",
)
async def reject_transfer(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    transfer_id: uuid.UUID = Path(..., description="The transfer ID"),
    payload: OwnershipRejectionCreate = Body(default_factory=OwnershipRejectionCreate),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OwnershipTransferResponse:
    service = WorkspaceTransferService()
    transfer = await service.reject_transfer(
        session=session,
        workspace_id=workspace_id,
        transfer_id=transfer_id,
        current_user_id=current_user.id,
        reason=payload.rejection_reason,
    )
    return _to_response_dto(transfer)


@router.post(
    "/{transfer_id}/cancel",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel workspace ownership nomination",
)
async def cancel_transfer(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    transfer_id: uuid.UUID = Path(..., description="The transfer ID"),
    owner_member: WorkspaceMember = Depends(require_active_workspace_owner),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OwnershipTransferResponse:
    service = WorkspaceTransferService()
    transfer = await service.cancel_transfer(
        session=session,
        workspace_id=workspace_id,
        transfer_id=transfer_id,
        current_user_id=current_user.id,
    )
    return _to_response_dto(transfer)


@router.get(
    "/active",
    response_model=Optional[OwnershipTransferResponse],
    status_code=status.HTTP_200_OK,
    summary="Get active pending ownership nomination for workspace",
)
async def get_active_transfer(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    member: WorkspaceMember = Depends(require_active_workspace_member),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Optional[OwnershipTransferResponse]:
    service = WorkspaceTransferService()
    transfer = await service.get_active_transfer(
        session=session,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
    )
    if not transfer:
        return None
    return _to_response_dto(transfer)


@router.post(
    "/{transfer_id}/former-owner-choice",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit former owner disposition choice (STAY or LEAVE)",
)
async def submit_former_owner_choice(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    transfer_id: uuid.UUID = Path(..., description="The transfer ID"),
    payload: FormerOwnerChoiceCreate = Body(...),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OwnershipTransferResponse:
    """Records the former owner's choice to either remain (STAY) or depart (LEAVE)."""
    service = WorkspaceTransferService()
    transfer = await service.record_former_owner_choice(
        session=session,
        workspace_id=workspace_id,
        transfer_id=transfer_id,
        current_user_id=current_user.id,
        choice=payload.choice,
        notes=payload.notes,
    )
    return _to_response_dto(transfer)


@router.post(
    "/{transfer_id}/role-decision",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Decide former owner role (ADMIN, MEMBER, or REMOVE)",
)
async def decide_former_owner_role(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    transfer_id: uuid.UUID = Path(..., description="The transfer ID"),
    payload: RoleDecisionCreate = Body(...),
    owner_member: WorkspaceMember = Depends(require_active_workspace_owner),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OwnershipTransferResponse:
    """Executes the new owner's role decision for the former owner (ADMIN, MEMBER, or REMOVE)."""
    service = WorkspaceTransferService()
    transfer = await service.decide_former_owner_role(
        session=session,
        workspace_id=workspace_id,
        transfer_id=transfer_id,
        current_user_id=current_user.id,
        decision=payload.decision,
        notes=payload.notes,
    )
    return _to_response_dto(transfer)

