"""Former OWNER Departure History Service.

Governed by Section 7 Batch 3 (WP 7.10, PO-D32-03).
Manages the creation, audit logging, and historical query access for
immutable former workspace owner departure records.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace_former_owner_departure import (
    FormerOwnerDepartureType,
    WorkspaceFormerOwnerDeparture,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.models.entities.workspace_ownership_transfer import WorkspaceOwnershipTransfer
from backend.repositories.workspace_former_owner_departure import (
    WorkspaceFormerOwnerDepartureRepository,
)

logger = structlog.get_logger(__name__)


class FormerOwnerDepartureService:
    """Service encapsulating former owner departure recording and audit history."""

    @staticmethod
    async def record_departure(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        former_owner_id: uuid.UUID,
        transfer_id: uuid.UUID,
        departure_type: FormerOwnerDepartureType | str,
        confirmed_by_user_id: uuid.UUID,
        former_role: str = "OWNER",
        retained_role: Optional[str] = None,
        departure_notes: Optional[str] = None,
        confirmed_at: Optional[datetime] = None,
    ) -> WorkspaceFormerOwnerDeparture:
        """
        Record an immutable former owner departure following ownership transfer completion or leave.
        Enforces canonical validation and emits an append-only audit log entry.
        """
        dep_type_str = (
            departure_type.value
            if isinstance(departure_type, FormerOwnerDepartureType)
            else str(departure_type)
        )

        valid_types = {t.value for t in FormerOwnerDepartureType}
        if dep_type_str not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid departure_type '{dep_type_str}'. Must be one of: {sorted(list(valid_types))}",
            )

        # Validate retained role consistency
        if dep_type_str == FormerOwnerDepartureType.NEW_OWNER_RETAINED.value:
            if retained_role not in (WorkspaceRole.ADMIN.value, WorkspaceRole.MEMBER.value):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="NEW_OWNER_RETAINED requires retained_role to be 'ADMIN' or 'MEMBER'",
                )
        else:
            if retained_role is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Departure type '{dep_type_str}' requires retained_role to be None",
                )

        effective_confirmed_at = confirmed_at or datetime.now(UTC)

        dep_repo = WorkspaceFormerOwnerDepartureRepository(session)
        departure = await dep_repo.create_departure(
            workspace_id=workspace_id,
            former_owner_id=former_owner_id,
            transfer_id=transfer_id,
            departure_type=dep_type_str,
            confirmed_by_user_id=confirmed_by_user_id,
            departure_confirmed_at=effective_confirmed_at,
            former_role=former_role,
            retained_role=retained_role,
            departure_notes=departure_notes,
        )

        # Record audit log entry
        audit_entry = AuditLog(
            action="WORKSPACE_FORMER_OWNER_DEPARTED",
            tenant_id=workspace_id,
            user_id=confirmed_by_user_id,
            resource_type="workspace_former_owner_departures",
            resource_id=str(departure.id),
            details={
                "workspace_id": str(workspace_id),
                "former_owner_id": str(former_owner_id),
                "transfer_id": str(transfer_id),
                "departure_type": dep_type_str,
                "former_role": former_role,
                "retained_role": retained_role,
                "confirmed_at": effective_confirmed_at.isoformat(),
            },
            status="SUCCESS",
        )
        session.add(audit_entry)
        await session.flush()

        logger.info(
            "Recorded former owner departure",
            departure_id=str(departure.id),
            workspace_id=str(workspace_id),
            former_owner_id=str(former_owner_id),
            departure_type=dep_type_str,
        )
        return departure

    @staticmethod
    async def list_workspace_departures(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        caller_user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[WorkspaceFormerOwnerDeparture]:
        """
        List historical departures for a workspace.
        Enforces caller membership validation.
        """
        # Validate caller is an active member
        mem_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == caller_user_id,
            WorkspaceMember.status == MemberStatus.ACTIVE.value,
            WorkspaceMember.is_deleted == False,
        )
        member = (await session.execute(mem_stmt)).scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: user is not an active member of this workspace",
            )

        dep_repo = WorkspaceFormerOwnerDepartureRepository(session)
        return await dep_repo.list_by_workspace(workspace_id, limit=limit, offset=offset)
