"""User Lifecycle and Deactivation Service.

Provides:
- Mandatory password re-authentication (or recent authentication check).
- Transactional sole-owner workspace protection.
- Soft-delete account deactivation (`is_deleted=True, is_active=False`).
- Full session & refresh token invalidation across DB and Redis.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.models.entities.user import User
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_ownership_transfer import (
    DecisionStatus,
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.models.entities.user_session import UserSession
from backend.models.entities.audit_log import AuditLog
from backend.core.security.password import verify_password
from backend.core.security.jwt import get_jwt_service

logger = structlog.get_logger(__name__)


@dataclass
class UserDeletionEligibilityResult:
    """Evaluation result for user deletion and deactivation eligibility (WP 7.9)."""

    eligible: bool
    rejection_code: Optional[str] = None
    rejection_reason: Optional[str] = None
    details: Optional[dict] = None


class LifecycleException(Exception):
    pass


class ReauthenticationFailedException(LifecycleException):
    pass


class UserDeletionIneligibleException(LifecycleException):
    """Raised when account deletion or deactivation is blocked under WP 7.9 gates."""

    def __init__(self, code: str, reason: str, details: Optional[dict] = None):
        self.code = code
        self.reason = reason
        self.details = details or {}
        super().__init__(f"{code}: {reason}")


class SoleWorkspaceOwnerConflictException(LifecycleException):
    def __init__(self, workspace_names: list[str]):
        self.workspace_names = workspace_names
        super().__init__(
            f"Cannot deactivate account. You are the sole owner of active workspace(s): "
            f"{', '.join(workspace_names)}. Please transfer ownership or delete the workspace first."
        )


class InactiveWorkspaceOwnerConflictException(LifecycleException):
    """Raised for Case C: owner of inactive, suspended, or deleted workspace (blocked under governance)."""
    def __init__(self, workspace_names: list[str]):
        self.workspace_names = workspace_names
        super().__init__(
            f"Cannot deactivate account. You hold an OWNER role in inactive or deleted workspace(s): "
            f"{', '.join(workspace_names)}. Owner deactivation for inactive workspaces is blocked."
        )


class UserLifecycleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.jwt_service = get_jwt_service()

    async def verify_credentials(self, user: User, password: str | None) -> None:
        """Verifies recent authentication credentials."""
        if not user.hashed_password:
            # If user has no password (e.g. SSO only), allow if confirmation text matches
            return

        if not password:
            raise ReauthenticationFailedException("Password re-authentication is required to deactivate account.")

        if not verify_password(password, user.hashed_password):
            logger.warning("Failed deactivation password attempt", user_id=str(user.id))
            raise ReauthenticationFailedException("Invalid password. Re-authentication failed.")

    async def check_sole_workspace_ownership(self, user_id: uuid.UUID) -> None:
        """
        Enforces sequential mutually exclusive deactivation decision logic (Decision D-17 / R5-01):
        Step 1 (Case A): If user has a non-deleted OWNER membership in an active workspace -> reject (HTTP 409).
        Step 2 (Case C): If user has a non-deleted OWNER membership in an inactive/deleted workspace -> reject (HTTP 409).
        Step 3 (Case B): Eligible non-owner or zero-membership user -> proceed.
        """
        # Step 1: Active workspace check (Case A)
        active_owned_stmt = (
            select(WorkspaceMember.workspace_id, Workspace.name)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.role == WorkspaceRole.OWNER.value,
                WorkspaceMember.is_deleted == False,
                Workspace.is_deleted == False,
                Workspace.status == WorkspaceStatus.ACTIVE.value,
            )
        )
        active_owned_rows = (await self.session.execute(active_owned_stmt)).all()
        if active_owned_rows:
            conflicts = [ws_name for _, ws_name in active_owned_rows]
            raise SoleWorkspaceOwnerConflictException(conflicts)

        # Step 2: Inactive / Suspended / Deleted workspace check (Case C)
        inactive_owned_stmt = (
            select(WorkspaceMember.workspace_id, Workspace.name)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.role == WorkspaceRole.OWNER.value,
                WorkspaceMember.is_deleted == False,
                (Workspace.is_deleted == True) | (Workspace.status != WorkspaceStatus.ACTIVE.value),
            )
        )
        inactive_owned_rows = (await self.session.execute(inactive_owned_stmt)).all()
        if inactive_owned_rows:
            conflicts = [ws_name for _, ws_name in inactive_owned_rows]
            raise InactiveWorkspaceOwnerConflictException(conflicts)

    async def validate_user_deletion_eligibility(
        self, user_id: uuid.UUID
    ) -> UserDeletionEligibilityResult:
        """
        Five-case evaluation gate for account deletion and deactivation (WP 7.9).
        1. Active Workspace Ownership -> USER_OWNS_ACTIVE_WORKSPACES
        2. Sole Eligible Admin in Ownerless Workspace -> USER_SOLE_RECOVERY_ADMIN
        3. Pending Nominee in In-Flight Transfer -> USER_HAS_PENDING_INCOMING_TRANSFERS
        4. Outgoing Former Owner with Pending Departure -> USER_HAS_PENDING_DEPARTURE_DECISION
        5. Eligible -> eligible=True
        """
        # Case 1: Active Workspace Ownership
        active_owned_stmt = (
            select(WorkspaceMember.workspace_id, Workspace.name)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.role == WorkspaceRole.OWNER.value,
                WorkspaceMember.status == MemberStatus.ACTIVE.value,
                WorkspaceMember.is_deleted == False,
                Workspace.is_deleted == False,
            )
        )
        active_owned_rows = (await self.session.execute(active_owned_stmt)).all()
        if active_owned_rows:
            ws_names = [name for _, name in active_owned_rows]
            return UserDeletionEligibilityResult(
                eligible=False,
                rejection_code="USER_OWNS_ACTIVE_WORKSPACES",
                rejection_reason=f"User owns active workspace(s): {', '.join(ws_names)}. Ownership must be transferred or workspace deleted prior to account deletion.",
                details={"workspaces": ws_names},
            )

        # Case 2: Sole Eligible Admin in Ownerless Workspace
        admin_stmt = (
            select(WorkspaceMember.workspace_id, Workspace.name)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.role == WorkspaceRole.ADMIN.value,
                WorkspaceMember.status == MemberStatus.ACTIVE.value,
                WorkspaceMember.is_deleted == False,
                Workspace.is_deleted == False,
            )
        )
        admin_rows = (await self.session.execute(admin_stmt)).all()
        for ws_id, ws_name in admin_rows:
            owner_count_stmt = select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == ws_id,
                WorkspaceMember.role == WorkspaceRole.OWNER.value,
                WorkspaceMember.status == MemberStatus.ACTIVE.value,
                WorkspaceMember.is_deleted == False,
            )
            has_owner = ((await self.session.execute(owner_count_stmt)).scalar() or 0) > 0
            if not has_owner:
                other_admin_stmt = select(func.count(WorkspaceMember.id)).where(
                    WorkspaceMember.workspace_id == ws_id,
                    WorkspaceMember.user_id != user_id,
                    WorkspaceMember.role == WorkspaceRole.ADMIN.value,
                    WorkspaceMember.status == MemberStatus.ACTIVE.value,
                    WorkspaceMember.is_deleted == False,
                )
                other_admins = (await self.session.execute(other_admin_stmt)).scalar() or 0
                if other_admins == 0:
                    return UserDeletionEligibilityResult(
                        eligible=False,
                        rejection_code="USER_SOLE_RECOVERY_ADMIN",
                        rejection_reason=f"User is the sole recovery admin in ownerless workspace '{ws_name}'",
                        details={"workspace_id": str(ws_id), "workspace_name": ws_name},
                    )

        # Case 3: Pending Nominee in In-Flight Transfer
        nominee_stmt = select(WorkspaceOwnershipTransfer.id, WorkspaceOwnershipTransfer.workspace_id).where(
            WorkspaceOwnershipTransfer.nominee_user_id == user_id,
            WorkspaceOwnershipTransfer.status == TransferStatus.PENDING.value,
        )
        nominee_rows = (await self.session.execute(nominee_stmt)).all()
        if nominee_rows:
            return UserDeletionEligibilityResult(
                eligible=False,
                rejection_code="USER_HAS_PENDING_INCOMING_TRANSFERS",
                rejection_reason=f"User is a nominated owner in {len(nominee_rows)} pending ownership transfer(s)",
                details={"pending_transfers": [str(t_id) for t_id, _ in nominee_rows]},
            )

        # Case 4: Outgoing Former Owner with Pending Departure
        departure_stmt = select(WorkspaceOwnershipTransfer.id, WorkspaceOwnershipTransfer.workspace_id).where(
            WorkspaceOwnershipTransfer.nominated_by_user_id == user_id,
            WorkspaceOwnershipTransfer.status == TransferStatus.ACCEPTED.value,
            WorkspaceOwnershipTransfer.decision_status == DecisionStatus.PENDING.value,
        )
        departure_rows = (await self.session.execute(departure_stmt)).all()
        if departure_rows:
            return UserDeletionEligibilityResult(
                eligible=False,
                rejection_code="USER_HAS_PENDING_DEPARTURE_DECISION",
                rejection_reason=f"User is an outgoing former owner with {len(departure_rows)} pending departure decision(s)",
                details={"pending_departure_transfers": [str(t_id) for t_id, _ in departure_rows]},
            )

        # Case 5: Eligible
        return UserDeletionEligibilityResult(eligible=True)

    async def deactivate_user_account(
        self,
        user_id: uuid.UUID,
        password: str | None = None,
        confirmation_text: str = ""
    ) -> None:
        """
        Atomically validates requirements, deactivates account, soft-deletes non-owner memberships,
        and revokes all sessions across DB and Redis.
        """
        if confirmation_text.strip().upper() != "DELETE":
            raise LifecycleException("Confirmation failed: you must type DELETE to confirm.")

        # 1. Lock user row first to serialize concurrent lifecycle changes (L_U)
        user_stmt = select(User).where(User.id == user_id).with_for_update()
        user = (await self.session.execute(user_stmt)).scalar_one_or_none()
        if not user or user.is_deleted or not user.is_active:
            raise LifecycleException("User not found or already deactivated.")

        # 2. Re-authentication check
        await self.verify_credentials(user, password)

        # 3. Identify ALL workspaces where user holds non-deleted memberships (both OWNER and non-owner)
        ws_ids_stmt = (
            select(WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id, WorkspaceMember.is_deleted == False)
            .distinct()
        )
        ws_ids_rows = (await self.session.execute(ws_ids_stmt)).scalars().all()
        affected_workspace_ids = sorted(list(set(ws_ids_rows)))

        # Lock affected workspaces in ascending order (L_W: Decision D-3.1 & Canonical Hierarchy)
        if affected_workspace_ids:
            ws_lock_stmt = (
                select(Workspace.id)
                .where(Workspace.id.in_(affected_workspace_ids))
                .order_by(Workspace.id.asc())
                .with_for_update()
            )
            await self.session.execute(ws_lock_stmt)

        # 4. Under workspace locks: evaluate sole ownership guards (Case A and Case C)
        # Aborts with SoleWorkspaceOwnerConflictException (Case A) or InactiveWorkspaceOwnerConflictException (Case C)
        await self.check_sole_workspace_ownership(user_id)

        # 4b. Evaluate full WP 7.9 Deletion Eligibility Gates
        eligibility = await self.validate_user_deletion_eligibility(user_id)
        if not eligibility.eligible:
            raise UserDeletionIneligibleException(
                code=eligibility.rejection_code or "USER_DELETION_INELIGIBLE",
                reason=eligibility.rejection_reason or "Account deletion criteria not met",
                details=eligibility.details,
            )

        # 5. Lock non-owner memberships in ascending order (L_WM: Case B)
        memberships_stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id, WorkspaceMember.is_deleted == False)
            .order_by(WorkspaceMember.id.asc())
            .with_for_update()
        )
        user_memberships = (await self.session.execute(memberships_stmt)).scalars().all()

        # 6. Execute Case B teardown: soft-delete non-owner memberships
        now = datetime.now(timezone.utc)
        for m in user_memberships:
            m.is_deleted = True
            m.updated_at = now
            self.session.add(m)

        # 7. Soft-delete user state
        user.is_active = False
        user.is_deleted = True
        user.updated_at = now
        self.session.add(user)

        # 7. Invalidate all UserSession entries in DB
        session_stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked == False)
            .values(is_revoked=True)
        )
        await self.session.execute(session_stmt)

        # 8. Record audit log entry in transaction
        audit_log = AuditLog(
            action="user.account.deactivated",
            user_id=user_id,
            resource_type="USER",
            resource_id=str(user_id),
            details={
                "memberships_deleted_count": len(user_memberships),
                "affected_workspaces": [str(ws_id) for ws_id in affected_workspace_ids],
            },
            status="success",
        )
        self.session.add(audit_log)

        await self.session.flush()
        await self.session.commit()

        # 9. Post-commit: Revoke user sessions in Redis / JWT blocklist
        try:
            # Revoke current token family if tracked
            await self.jwt_service.revoke_user_tokens(str(user_id))
        except Exception as e:
            logger.warning("Redis token revocation completed with notice", error=str(e))

        logger.info("User account successfully deactivated", user_id=str(user_id))
