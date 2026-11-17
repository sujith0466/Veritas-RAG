"""Ownerless Workspace Recovery Service (DEC-01 / WP-6).

Implements the multi-factor, audited Platform Admin recovery workflow under
Project Owner Decisions D-3.1 through D-3.7 and Option 3A:
1. Re-verification of Platform Admin authority and target eligibility directly against
   the PostgreSQL `users` table under deterministic ascending row-level locking (D-3.7 Option B).
2. Pessimistic row-level locking on workspaces (SELECT ... FOR UPDATE).
3. Option 3A preflight check: fail-closed rejection with HTTP 409 if any non-deleted
   OWNER membership exists (including canonical OWNER, legacy workspace_owner, casing, and whitespace variants).
4. Validation that the target user is an active member of the workspace.
5. Promotion of the target member to OWNER with mandatory justification ticket and
   append-only transactional AuditLog recording.
6. Two-tiered exception handling preserving intentional HTTP rejections and tracking
   rollback/invalidation states truthfully on persistence failure.
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.owner_recovery import OwnerRecoveryRequest, OwnerRecoveryResponse
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole

logger = structlog.get_logger(__name__)


class OwnerRecoveryService:
    """Service encapsulating the transactional ownerless workspace recovery workflow."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def recover_ownerless_workspace(
        self,
        workspace_id: uuid.UUID,
        caller_user_id: uuid.UUID,
        request: OwnerRecoveryRequest,
    ) -> OwnerRecoveryResponse:
        """Execute atomic break-glass recovery of an ownerless workspace."""
        target_member = None
        previous_role = None
        previous_version = None

        try:
            # 1. Deterministic User Row Locking (Decision D-3.7 Option B)
            # Sort caller and target IDs in ascending primary-key order to avoid circular wait
            user_ids = sorted(list(set([caller_user_id, request.target_user_id])))
            locked_users: dict[uuid.UUID, User] = {}

            for uid in user_ids:
                user_stmt = (
                    select(User)
                    .where(User.id == uid, User.is_deleted.is_(False))
                    .with_for_update()
                )
                user_res = await self.session.execute(user_stmt)
                user_obj = user_res.scalar_one_or_none()
                if user_obj is not None:
                    locked_users[uid] = user_obj

            # 2. Authoritative Caller Verification under row lock
            caller = locked_users.get(caller_user_id)
            if not caller:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Caller user record not found or deactivated.",
                )

            if not caller.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Caller account is deactivated.",
                )

            caller_role = (caller.role or "").strip().lower()
            if caller_role != "platform_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Authoritative platform admin verification failed: caller is not a platform admin in the database.",
                )

            # 3. Target User Account Verification under row lock
            target_user = locked_users.get(request.target_user_id)
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target user record not found or has been deleted.",
                )

            if not target_user.is_active or not target_user.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target user account is inactive or unverified.",
                )

            # 4. Pessimistic row-level lock on the target workspace
            ws_stmt = (
                select(Workspace)
                .where(Workspace.id == workspace_id, Workspace.is_deleted.is_(False))
                .with_for_update()
            )
            ws_res = await self.session.execute(ws_stmt)
            workspace = ws_res.scalar_one_or_none()
            if not workspace:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target workspace not found or has been deleted.",
                )

            # 5. Option 3A Precondition Check: Fail-closed verification of zero non-deleted owners
            # Matches canonical OWNER and confirmed historical alias WORKSPACE_OWNER
            # Bounded ASCII whitespace stripping: space (0x20), tab (0x09), carriage return (0x0D), newline (0x0A)
            clean_role_expr = func.btrim(func.upper(WorkspaceMember.role), " \t\r\n")
            owner_stmt = (
                select(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.is_deleted.is_(False),
                    clean_role_expr.in_(["OWNER", "WORKSPACE_OWNER"]),
                )
                .with_for_update()
            )
            owner_res = await self.session.execute(owner_stmt)
            existing_owners = owner_res.scalars().all()
            if len(existing_owners) > 0:
                has_active = any(o.status == MemberStatus.ACTIVE.value for o in existing_owners)
                if has_active:
                    detail_msg = f"Recovery rejected: workspace currently has {len(existing_owners)} active OWNER(s). Only ownerless workspaces may be recovered."
                else:
                    detail_msg = f"Recovery rejected: workspace contains {len(existing_owners)} non-deleted OWNER record(s) (Option 3A). Only ownerless workspaces may be recovered."
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=detail_msg,
                )

            # 6. Target workspace member validation: must be an active member of this workspace
            target_stmt = (
                select(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == request.target_user_id,
                    WorkspaceMember.status == MemberStatus.ACTIVE.value,
                    WorkspaceMember.is_deleted.is_(False),
                )
                .with_for_update()
            )
            target_res = await self.session.execute(target_stmt)
            target_member = target_res.scalar_one_or_none()
            if not target_member:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target user is not an active member of this workspace.",
                )

            # 7. Mutate target member role to OWNER and advance version counter
            previous_role = target_member.role
            previous_version = target_member.version

            target_member.role = WorkspaceRole.OWNER.value
            target_member.version = (previous_version or 0) + 1
            self.session.add(target_member)

            # 8. Append-only transactional AuditLog recording
            recovered_timestamp = datetime.now(UTC).isoformat()
            audit_log = AuditLog(
                tenant_id=workspace_id,
                action="WORKSPACE_OWNER_RECOVERED",
                user_id=caller_user_id,
                resource_type="workspace",
                resource_id=str(workspace_id),
                details={
                    "justification_ticket_id": request.justification_ticket_id,
                    "justification_reason": request.justification_reason,
                    "promoted_user_id": str(request.target_user_id),
                    "previous_role": previous_role,
                    "new_role": WorkspaceRole.OWNER.value,
                    "previous_version": previous_version,
                    "new_version": target_member.version,
                    "recovered_at": recovered_timestamp,
                },
                status="success",
            )
            self.session.add(audit_log)
            await self.session.flush()
            await self.session.commit()

            logger.info(
                "workspace_owner_recovered",
                workspace_id=str(workspace_id),
                promoted_user_id=str(request.target_user_id),
                previous_role=previous_role,
                caller_user_id=str(caller_user_id),
                ticket_id=request.justification_ticket_id,
            )

            return OwnerRecoveryResponse(
                workspace_id=workspace_id,
                promoted_user_id=request.target_user_id,
                previous_role=previous_role,
                new_role=WorkspaceRole.OWNER.value,
                justification_ticket_id=request.justification_ticket_id,
                recovered_at=recovered_timestamp,
                recovery_status="COMPLETED",
            )

        except HTTPException:
            # Tier 1: Intentional HTTP rejection (400, 403, 404, 409)
            # Attempt rollback to release any acquired row locks
            try:
                await self.session.rollback()
            except Exception as rb_exc:
                logger.error(
                    "owner_recovery_rollback_failed_on_http_rejection",
                    error=str(rb_exc),
                    workspace_id=str(workspace_id),
                )
                try:
                    await self.session.invalidate()
                    logger.warning(
                        "owner_recovery_session_invalidated_after_http_rollback_failure",
                        workspace_id=str(workspace_id),
                    )
                except Exception as inv_exc:
                    logger.critical(
                        "owner_recovery_fatal_session_leak_on_http_rejection",
                        rollback_error=str(rb_exc),
                        invalidation_error=str(inv_exc),
                        workspace_id=str(workspace_id),
                        caller_user_id=str(caller_user_id),
                        target_user_id=str(request.target_user_id),
                        detail="Both rollback and connection invalidation failed on HTTP rejection.",
                    )
            # Bare raise preserves original exception instance, status, detail, and traceback
            raise

        except Exception as primary_exc:
            # Tier 2: Unexpected persistence or driver failure
            if target_member is not None and previous_role is not None:
                target_member.role = previous_role
                target_member.version = previous_version
                try:
                    self.session.expunge(target_member)
                except Exception:
                    pass

            rollback_succeeded = False
            invalidation_succeeded = False

            try:
                await self.session.rollback()
                rollback_succeeded = True
                logger.info("owner_recovery_rollback_succeeded", workspace_id=str(workspace_id))
            except Exception as rb_exc:
                logger.error(
                    "owner_recovery_rollback_failed_on_persistence_error",
                    error=str(rb_exc),
                    primary_error=str(primary_exc),
                    workspace_id=str(workspace_id),
                )
                try:
                    await self.session.invalidate()
                    invalidation_succeeded = True
                    logger.warning(
                        "owner_recovery_session_invalidated_after_persistence_rollback_failure",
                        workspace_id=str(workspace_id),
                    )
                except Exception as inv_exc:
                    logger.critical(
                        "owner_recovery_fatal_session_leak_on_persistence_error",
                        primary_error=str(primary_exc),
                        rollback_error=str(rb_exc),
                        invalidation_error=str(inv_exc),
                        workspace_id=str(workspace_id),
                        caller_user_id=str(caller_user_id),
                        target_user_id=str(request.target_user_id),
                        detail="Both rollback and connection invalidation failed. Connection pool integrity cannot be guaranteed.",
                    )

            if rollback_succeeded:
                detail_msg = "Owner recovery failed during mutation or audit persistence: transaction rolled back."
            elif invalidation_succeeded:
                detail_msg = "Owner recovery failed: transaction rollback failed; database session was invalidated to protect connection pool."
            else:
                detail_msg = "Owner recovery failed: critical persistence failure; both transaction rollback and session invalidation failed."

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail_msg,
            ) from primary_exc
