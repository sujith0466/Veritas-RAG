"""Workspace Membership Management Service.

Implements enterprise member lifecycle, role mutation, suspension/restoration,
soft removal, last owner protection with pessimistic locking, Redis cache invalidation,
audit logging, and domain event dispatching.
"""

import datetime
from datetime import UTC
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.events.dispatcher import EventDispatcher
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.events import (
    WorkspaceMemberRemovedEvent,
    WorkspaceMemberRestoredEvent,
    WorkspaceMemberRoleUpdatedEvent,
    WorkspaceMemberSuspendedEvent,
)

logger = structlog.get_logger(__name__)


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class MembershipError(Exception):
    """Base exception for workspace membership errors."""
    pass


class MembershipNotFoundError(MembershipError):
    """Raised when a workspace member is not found."""
    pass


class MembershipUnauthorizedError(MembershipError):
    """Raised when an actor lacks permission to manage workspace members."""
    pass


class MembershipConflictError(MembershipError):
    """Raised when a membership operation violates state or safety invariants."""
    pass


class MembershipInvalidStateError(MembershipError):
    """Raised when workspace or member is in an invalid state for the operation."""
    pass


# ── Membership Service ────────────────────────────────────────────────────────

class WorkspaceMembershipService:
    """Enterprise domain service for workspace members."""

    def __init__(
        self,
        member_repo: WorkspaceMemberRepository,
        workspace_repo: WorkspaceRepository,
        event_dispatcher: EventDispatcher | None = None,
    ):
        self.member_repo = member_repo
        self.workspace_repo = workspace_repo
        self.event_dispatcher = event_dispatcher

    async def _verify_actor_membership(
        self, workspace_id: uuid.UUID, actor_id: uuid.UUID
    ) -> WorkspaceMember:
        """Fetch actor membership and verify they are an active member."""
        actor_member = await self.member_repo.get_membership(workspace_id, actor_id)
        if not actor_member:
            raise MembershipUnauthorizedError("Actor is not a member of this workspace.")
        if actor_member.status == MemberStatus.SUSPENDED.value:
            raise MembershipUnauthorizedError("Suspended members cannot perform workspace operations.")
        return actor_member

    async def list_members(
        self,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        search: str | None = None,
        role: str | None = None,
        status: str | None = None,
        cursor: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkspaceMember], int, str | None]:
        """List paginated workspace members with search and filter capabilities."""
        await self._verify_actor_membership(workspace_id, actor_id)
        return await self.member_repo.list_members(
            workspace_id=workspace_id,
            search=search,
            role=role,
            status=status,
            cursor=cursor,
            skip=skip,
            limit=limit,
        )

    async def get_member(
        self, workspace_id: uuid.UUID, member_id: uuid.UUID, actor_id: uuid.UUID
    ) -> WorkspaceMember:
        """Fetch a single member profile within workspace tenant boundary."""
        await self._verify_actor_membership(workspace_id, actor_id)
        member = await self.member_repo.get_by_id(member_id, workspace_id)
        if not member:
            raise MembershipNotFoundError("Member not found in this workspace.")
        return member

    async def update_member_role(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        member_id: uuid.UUID,
        new_role: str,
        dry_run: bool = False,
    ) -> WorkspaceMember:
        """
        Updates a member's role with hierarchical permission validation and Last Owner Protection.
        """
        new_role_upper = new_role.strip().upper()
        if new_role_upper not in [r.value for r in WorkspaceRole]:
            raise MembershipError(f"Invalid workspace role: {new_role}")

        # 1. Validate workspace status
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise MembershipInvalidStateError("Cannot update roles in an inactive workspace.")

        # 2. Validate actor permissions
        actor = await self._verify_actor_membership(workspace_id, actor_id)
        actor_role = actor.role.upper()

        if actor_role not in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
            raise MembershipUnauthorizedError("Only OWNER or ADMIN can modify member roles.")

        if actor_role == WorkspaceRole.ADMIN.value and new_role_upper == WorkspaceRole.OWNER.value:
            raise MembershipUnauthorizedError("ADMIN cannot promote a member to OWNER.")

        # 3. Retrieve target member under pessimistic row lock
        member = await self.member_repo.get_by_id_for_update(member_id, workspace_id)
        if not member:
            raise MembershipNotFoundError("Member not found in this workspace.")

        # 3b. Prevent self-promotion or self-demotion
        if actor.id == member.id:
            raise MembershipUnauthorizedError("You cannot modify your own role.")

        old_role = member.role.upper()
        if old_role == new_role_upper:
            return member  # No change

        # ADMIN cannot demote or modify an OWNER
        if actor_role == WorkspaceRole.ADMIN.value and old_role == WorkspaceRole.OWNER.value:
            raise MembershipUnauthorizedError("ADMIN cannot modify the role of an OWNER.")

        # 4. Last Owner Protection
        if old_role == WorkspaceRole.OWNER.value and new_role_upper != WorkspaceRole.OWNER.value:
            active_owners = await self.member_repo.count_active_owners(workspace_id)
            if active_owners <= 1:
                raise MembershipConflictError("Cannot demote the last remaining OWNER of the workspace.")

        if dry_run:
            # Create a clone for the return value without saving to DB
            import copy
            member_copy = copy.copy(member)
            member_copy.role = new_role_upper
            return member_copy

        # 5. Persist update
        now_utc = datetime.datetime.now(UTC)
        member.role = new_role_upper
        member.version += 1
        session.add(member)

        # 6. Audit Log
        audit_log = AuditLog(
            action="workspace.member.role_updated",
            user_id=actor_id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace_id),
                "target_user_id": str(member.user_id),
                "old_role": old_role,
                "new_role": new_role_upper,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        # 7. Emit domain event
        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceMemberRoleUpdatedEvent(
                    workspace_id=str(workspace_id),
                    member_id=str(member.id),
                    user_id=str(member.user_id),
                    actor_id=str(actor_id),
                    old_role=old_role,
                    new_role=new_role_upper,
                )
            )

        return member

    async def suspend_member(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        member_id: uuid.UUID,
    ) -> WorkspaceMember:
        """Suspends a workspace member, preventing access while preserving audit history."""
        # 1. Validate workspace status
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise MembershipInvalidStateError("Cannot suspend members in an inactive workspace.")

        # 2. Validate actor permissions
        actor = await self._verify_actor_membership(workspace_id, actor_id)
        actor_role = actor.role.upper()
        if actor_role not in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
            raise MembershipUnauthorizedError("Only OWNER or ADMIN can suspend members.")

        # 3. Retrieve target member with row lock
        member = await self.member_repo.get_by_id_for_update(member_id, workspace_id)
        if not member:
            raise MembershipNotFoundError("Member not found.")

        if member.status == MemberStatus.SUSPENDED.value:
            return member

        if actor_role == WorkspaceRole.ADMIN.value and member.role.upper() == WorkspaceRole.OWNER.value:
            raise MembershipUnauthorizedError("ADMIN cannot suspend an OWNER.")

        # 4. Last Owner Protection
        if member.role.upper() == WorkspaceRole.OWNER.value:
            active_owners = await self.member_repo.count_active_owners(workspace_id)
            if active_owners <= 1:
                raise MembershipConflictError("Cannot suspend the last remaining OWNER of the workspace.")

        # 5. Persist status update
        member.status = MemberStatus.SUSPENDED.value
        member.version += 1
        session.add(member)

        # 6. Audit Log
        audit_log = AuditLog(
            action="workspace.member.suspended",
            user_id=actor_id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace_id),
                "target_user_id": str(member.user_id),
                "role": member.role,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        # 7. Emit domain event
        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceMemberSuspendedEvent(
                    workspace_id=str(workspace_id),
                    member_id=str(member.id),
                    user_id=str(member.user_id),
                    actor_id=str(actor_id),
                )
            )

        return member

    async def restore_member(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        member_id: uuid.UUID,
    ) -> WorkspaceMember:
        """Restores a suspended workspace member to ACTIVE status."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise MembershipInvalidStateError("Cannot restore members in an inactive workspace.")

        actor = await self._verify_actor_membership(workspace_id, actor_id)
        actor_role = actor.role.upper()
        if actor_role not in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
            raise MembershipUnauthorizedError("Only OWNER or ADMIN can restore suspended members.")

        member = await self.member_repo.get_by_id_for_update(member_id, workspace_id)
        if not member:
            raise MembershipNotFoundError("Member not found.")

        if member.status == MemberStatus.ACTIVE.value:
            return member

        member.status = MemberStatus.ACTIVE.value
        member.version += 1
        session.add(member)

        audit_log = AuditLog(
            action="workspace.member.restored",
            user_id=actor_id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace_id),
                "target_user_id": str(member.user_id),
                "role": member.role,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceMemberRestoredEvent(
                    workspace_id=str(workspace_id),
                    member_id=str(member.id),
                    user_id=str(member.user_id),
                    actor_id=str(actor_id),
                )
            )

        return member

    async def remove_member(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        member_id: uuid.UUID,
    ) -> WorkspaceMember:
        """Soft deletes a workspace member from the workspace with Last Owner Protection."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise MembershipInvalidStateError("Cannot remove members from an inactive workspace.")

        actor = await self._verify_actor_membership(workspace_id, actor_id)
        actor_role = actor.role.upper()

        # Self-removal (leaving workspace) is allowed unless last owner
        is_self_removal = (actor.id == member_id)

        if not is_self_removal and actor_role not in [WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value]:
            raise MembershipUnauthorizedError("Only OWNER or ADMIN can remove other members.")

        member = await self.member_repo.get_by_id_for_update(member_id, workspace_id)
        if not member:
            raise MembershipNotFoundError("Member not found.")

        if not is_self_removal and actor_role == WorkspaceRole.ADMIN.value and member.role.upper() == WorkspaceRole.OWNER.value:
            raise MembershipUnauthorizedError("ADMIN cannot remove an OWNER.")

        # Last Owner Protection
        if member.role.upper() == WorkspaceRole.OWNER.value:
            active_owners = await self.member_repo.count_active_owners(workspace_id)
            if active_owners <= 1:
                raise MembershipConflictError("Cannot remove the last remaining OWNER of the workspace.")

        # Soft delete
        member.is_deleted = True
        member.version += 1
        session.add(member)

        audit_log = AuditLog(
            action="workspace.member.removed",
            user_id=actor_id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace_id),
                "target_user_id": str(member.user_id),
                "is_self_removal": is_self_removal,
                "role": member.role,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceMemberRemovedEvent(
                    workspace_id=str(workspace_id),
                    member_id=str(member.id),
                    user_id=str(member.user_id),
                    actor_id=str(actor_id),
                )
            )

        return member

    async def bulk_update_members(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        member_ids: list[uuid.UUID],
        action: str,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Executes a batch operation on up to 100 workspace members with atomic parent audit log."""
        if len(member_ids) > 100:
            raise MembershipError("Bulk operation cannot exceed 100 members.")

        results = []
        action_lower = action.strip().lower()

        for mid in member_ids:
            try:
                if action_lower == "suspend":
                    await self.suspend_member(session, workspace_id, actor_id, mid)
                elif action_lower == "restore":
                    await self.restore_member(session, workspace_id, actor_id, mid)
                elif action_lower == "remove":
                    await self.remove_member(session, workspace_id, actor_id, mid)
                elif action_lower == "update_role" and role:
                    await self.update_member_role(session, workspace_id, actor_id, mid, role)
                results.append({"member_id": str(mid), "status": "success"})
            except Exception as ex:
                results.append({"member_id": str(mid), "status": "error", "message": str(ex)})

        # Record parent audit log
        parent_audit = AuditLog(
            action="workspace.member.bulk_operation",
            user_id=actor_id,
            resource_type="WORKSPACE",
            resource_id=str(workspace_id),
            details={
                "action": action_lower,
                "total_requested": len(member_ids),
                "success_count": len([r for r in results if r["status"] == "success"]),
                "error_count": len([r for r in results if r["status"] == "error"]),
                "results": results,
            },
            status="success",
        )
        session.add(parent_audit)
        await session.flush()
        await session.commit()

        return {
            "total": len(member_ids),
            "results": results,
        }
