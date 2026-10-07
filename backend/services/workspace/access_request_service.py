"""Workspace Access Request Management Service.

Implements role elevation requests, join code approval gating, transactional row-lock approval,
rejection with audit trails, and multi-tenant isolation.
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import WorkspaceStatus
from backend.models.entities.workspace_access_request import (
    AccessRequestStatus,
    AccessRequestType,
    WorkspaceAccessRequest,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_access_request import WorkspaceAccessRequestRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository

logger = structlog.get_logger(__name__)


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class AccessRequestError(Exception):
    """Base exception for access request operations."""
    pass


class AccessRequestNotFoundError(AccessRequestError):
    """Raised when an access request is not found."""
    pass


class AccessRequestUnauthorizedError(AccessRequestError):
    """Raised when an actor lacks permission to manage or submit an access request."""
    pass


class AccessRequestConflictError(AccessRequestError):
    """Raised when an access request conflicts with existing state (e.g., duplicate pending)."""
    pass


class AccessRequestInvalidStateError(AccessRequestError):
    """Raised when an access request or workspace is in an invalid state for the operation."""
    pass


# ── Service Implementation ───────────────────────────────────────────────────

class AccessRequestService:
    """Service handling the lifecycle of role elevation and join approval requests."""

    def __init__(
        self,
        access_repo: WorkspaceAccessRequestRepository,
        member_repo: WorkspaceMemberRepository,
        workspace_repo: WorkspaceRepository,
    ) -> None:
        self.access_repo = access_repo
        self.member_repo = member_repo
        self.workspace_repo = workspace_repo

    async def _verify_actor_admin(
        self, workspace_id: uuid.UUID, actor_id: uuid.UUID
    ) -> WorkspaceMember:
        """Verifies caller is an active OWNER or ADMIN in the workspace."""
        actor = await self.member_repo.get_membership(workspace_id, actor_id)
        if not actor or actor.status != MemberStatus.ACTIVE.value:
            raise AccessRequestUnauthorizedError("Caller is not an active member of this workspace.")
        if actor.role.upper() not in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
            raise AccessRequestUnauthorizedError("Only OWNER or ADMIN can review access requests.")
        return actor

    async def create_request(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_type: str,
        requested_role: str,
        reason: str | None = None,
        current_role: str | None = None,
    ) -> WorkspaceAccessRequest:
        """Submits a new access request with duplicate prevention and authorization checks."""
        # 1. Validate workspace status
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise AccessRequestInvalidStateError("Cannot request access to an inactive or non-existent workspace.")

        type_upper = request_type.upper()
        if type_upper not in [AccessRequestType.ROLE_ELEVATION.value, AccessRequestType.JOIN_APPROVAL.value]:
            raise AccessRequestInvalidStateError(f"Invalid access request type: {request_type}")

        requested_role_upper = requested_role.upper()
        if requested_role_upper not in [WorkspaceRole.ADMIN.value, WorkspaceRole.MEMBER.value, WorkspaceRole.VIEWER.value]:
            raise AccessRequestInvalidStateError(f"Invalid requested role: {requested_role}")

        # 2. Check for existing active pending request of the same type
        existing_pending = await self.access_repo.get_active_pending(workspace_id, actor_id, type_upper)
        if existing_pending:
            raise AccessRequestConflictError(
                f"You already have an active pending {type_upper.replace('_', ' ').lower()} request for this workspace."
            )

        resolved_current_role: str | None = None

        if type_upper == AccessRequestType.ROLE_ELEVATION.value:
            # Caller MUST be an active member in the workspace
            member = await self.member_repo.get_membership(workspace_id, actor_id)
            if not member or member.status != MemberStatus.ACTIVE.value:
                raise AccessRequestUnauthorizedError("You must be an active workspace member to request role elevation.")

            resolved_current_role = member.role.upper()
            if resolved_current_role in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
                raise AccessRequestConflictError(f"You already have {resolved_current_role} privileges.")

            if resolved_current_role == requested_role_upper:
                raise AccessRequestConflictError(f"You already have the role {requested_role_upper}.")

        elif type_upper == AccessRequestType.JOIN_APPROVAL.value:
            # Caller is an authenticated prospective joiner; must NOT already be an active member
            existing_member = await self.member_repo.get_membership(workspace_id, actor_id)
            if existing_member and existing_member.status == MemberStatus.ACTIVE.value:
                raise AccessRequestConflictError("You are already an active member of this workspace.")
            resolved_current_role = None

        # 3. Create persistent entity
        access_request = WorkspaceAccessRequest(
            workspace_id=workspace_id,
            user_id=actor_id,
            request_type=type_upper,
            current_role=resolved_current_role,
            requested_role=requested_role_upper,
            status=AccessRequestStatus.PENDING.value,
            reason=reason.strip() if reason else None,
        )
        session.add(access_request)
        await session.flush()

        # 4. Audit Log
        audit_log = AuditLog(
            action="workspace.access_request.created",
            user_id=actor_id,
            resource_type="WORKSPACE_ACCESS_REQUEST",
            resource_id=str(access_request.id),
            details={
                "workspace_id": str(workspace_id),
                "request_type": type_upper,
                "current_role": resolved_current_role,
                "requested_role": requested_role_upper,
            },
            status="success",
        )
        session.add(audit_log)
        await session.commit()
        await session.refresh(access_request)

        logger.info(
            "Access request submitted successfully",
            request_id=str(access_request.id),
            workspace_id=str(workspace_id),
            user_id=str(actor_id),
            request_type=type_upper,
        )
        return access_request

    async def list_requests(
        self,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkspaceAccessRequest], int]:
        """Lists access requests for a workspace with role authorization."""
        await self._verify_actor_admin(workspace_id, actor_id)
        return await self.access_repo.list_by_workspace(
            workspace_id=workspace_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def approve_request(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> WorkspaceAccessRequest:
        """Approves an access request with ACID pessimistic row lock revalidation."""
        # 1. Authorize actor
        actor = await self._verify_actor_admin(workspace_id, actor_id)

        # 2. Acquire row lock on access request
        req = await self.access_repo.get_by_id_for_update(request_id, workspace_id)
        if not req:
            raise AccessRequestNotFoundError("Access request not found.")
        if req.status != AccessRequestStatus.PENDING.value:
            raise AccessRequestConflictError(f"Cannot approve request with status '{req.status}'.")

        # 3. Validate workspace status
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise AccessRequestInvalidStateError("Cannot approve requests for an inactive workspace.")

        now_utc = datetime.now(UTC)

        # 4. Handle request type semantics
        if req.request_type == AccessRequestType.ROLE_ELEVATION.value:
            # Revalidate member row under row lock
            member = await self.member_repo.get_by_id_for_update(req.user_id, workspace_id)
            if not member:
                raise AccessRequestConflictError("Target user is no longer a member of this workspace.")
            if member.status != MemberStatus.ACTIVE.value:
                raise AccessRequestConflictError(f"Cannot elevate member with status '{member.status}'.")
            if req.current_role and member.role.upper() != req.current_role.upper():
                raise AccessRequestConflictError("Member role has changed since request submission.")

            # Admin cannot elevate anyone to OWNER
            if actor.role.upper() == WorkspaceRole.ADMIN.value and req.requested_role.upper() == WorkspaceRole.OWNER.value:
                raise AccessRequestUnauthorizedError("ADMIN cannot approve role elevation to OWNER.")

            # Elevate member role
            member.role = req.requested_role.upper()
            member.version += 1
            session.add(member)

        elif req.request_type == AccessRequestType.JOIN_APPROVAL.value:
            # Revalidate user is not already an active member
            existing_member = await self.member_repo.get_membership(workspace_id, req.user_id)
            if existing_member and existing_member.status == MemberStatus.ACTIVE.value:
                raise AccessRequestConflictError("User is already an active member of this workspace.")

            if existing_member and existing_member.status == MemberStatus.SUSPENDED.value:
                existing_member.status = MemberStatus.ACTIVE.value
                existing_member.role = req.requested_role.upper()
                existing_member.version += 1
                session.add(existing_member)
            else:
                new_member = WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=req.user_id,
                    role=req.requested_role.upper(),
                    status=MemberStatus.ACTIVE.value,
                    joined_at=now_utc,
                    version=1,
                )
                session.add(new_member)

        # 5. Transition request status
        req.status = AccessRequestStatus.APPROVED.value
        req.reviewed_by_id = actor_id
        req.reviewed_at = now_utc
        session.add(req)

        # 6. Audit Log
        audit_log = AuditLog(
            action="workspace.access_request.approved",
            user_id=actor_id,
            resource_type="WORKSPACE_ACCESS_REQUEST",
            resource_id=str(req.id),
            details={
                "workspace_id": str(workspace_id),
                "request_type": req.request_type,
                "target_user_id": str(req.user_id),
                "granted_role": req.requested_role,
            },
            status="success",
        )
        session.add(audit_log)
        await session.commit()
        await session.refresh(req)

        logger.info(
            "Access request approved",
            request_id=str(req.id),
            workspace_id=str(workspace_id),
            target_user_id=str(req.user_id),
            actor_id=str(actor_id),
        )
        return req

    async def reject_request(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_id: uuid.UUID,
        rejection_reason: str | None = None,
    ) -> WorkspaceAccessRequest:
        """Rejects an access request with transactional row lock revalidation."""
        await self._verify_actor_admin(workspace_id, actor_id)

        req = await self.access_repo.get_by_id_for_update(request_id, workspace_id)
        if not req:
            raise AccessRequestNotFoundError("Access request not found.")
        if req.status != AccessRequestStatus.PENDING.value:
            raise AccessRequestConflictError(f"Cannot reject request with status '{req.status}'.")

        now_utc = datetime.now(UTC)
        req.status = AccessRequestStatus.REJECTED.value
        req.reviewed_by_id = actor_id
        req.reviewed_at = now_utc
        req.rejection_reason = rejection_reason.strip() if rejection_reason else None
        session.add(req)

        audit_log = AuditLog(
            action="workspace.access_request.rejected",
            user_id=actor_id,
            resource_type="WORKSPACE_ACCESS_REQUEST",
            resource_id=str(req.id),
            details={
                "workspace_id": str(workspace_id),
                "request_type": req.request_type,
                "target_user_id": str(req.user_id),
                "rejection_reason": req.rejection_reason,
            },
            status="success",
        )
        session.add(audit_log)
        await session.commit()
        await session.refresh(req)

        logger.info(
            "Access request rejected",
            request_id=str(req.id),
            workspace_id=str(workspace_id),
            target_user_id=str(req.user_id),
            actor_id=str(actor_id),
        )
        return req
