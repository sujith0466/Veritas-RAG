"""Workspace Invitation Service.

Implements enterprise invitation workflows, cryptographic token generation,
TTL calculation, rate limiting, duplicate handling, resilient async email dispatch,
and audit logging.
"""

import datetime
from datetime import UTC
import hashlib
import secrets
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.events.dispatcher import EventDispatcher
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_member import WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_invitation import WorkspaceInvitationRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.services.email.provider import EmailProvider
from backend.services.workspace.events import (
    WorkspaceInvitationAcceptedEvent,
    WorkspaceInvitationCreatedEvent,
    WorkspaceInvitationExpiredEvent,
    WorkspaceInvitationResentEvent,
    WorkspaceInvitationRevokedEvent,
)

logger = structlog.get_logger(__name__)


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class InvitationError(Exception):
    """Base exception for invitation errors."""
    pass


class InvitationNotFoundError(InvitationError):
    """Raised when an invitation is not found within the workspace boundary."""
    pass


class InvitationUnauthorizedError(InvitationError):
    """Raised when the actor lacks permission to manage invitations."""
    pass


class InvitationConflictError(InvitationError):
    """Raised when an invitation or membership conflict occurs (409 Conflict)."""
    pass


class InvitationRateLimitError(InvitationError):
    """Raised when invitation rate limits are exceeded (429 Too Many Requests)."""
    pass


class InvitationInvalidStateError(InvitationError):
    """Raised when an invitation is in an invalid state for the requested operation."""
    pass


# ── Token Generation ──────────────────────────────────────────────────────────

def generate_invitation_token() -> tuple[str, str]:
    """
    Generates a secure high-entropy invitation token.

    Returns:
        tuple[str, str]: (raw_token, token_hash)
        - raw_token is sent ONLY to the recipient via email.
        - token_hash is stored in the database (SHA-256).
    """
    raw_token = f"sec_inv_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw invitation token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


# ── In-Memory / Sliding Window Rate Limiter ───────────────────────────────────

class InvitationRateLimiter:
    """Tracks invitation rate limits across workspace, inviter, and target email."""

    def __init__(self) -> None:
        self._workspace_timestamps: dict[str, list[datetime.datetime]] = {}
        self._inviter_timestamps: dict[str, list[datetime.datetime]] = {}
        self._email_timestamps: dict[str, list[datetime.datetime]] = {}

    def check_and_record(
        self, workspace_id: uuid.UUID, inviter_id: uuid.UUID, email: str
    ) -> None:
        now = datetime.datetime.now(UTC)
        one_hour_ago = now - datetime.timedelta(hours=1)
        one_day_ago = now - datetime.timedelta(days=1)

        ws_key = str(workspace_id)
        inv_key = str(inviter_id)
        email_key = email.strip().lower()

        # Workspace limit: 100/hour
        ws_list = [t for t in self._workspace_timestamps.get(ws_key, []) if t > one_hour_ago]
        if len(ws_list) >= 100:
            raise InvitationRateLimitError("Workspace invitation rate limit exceeded (max 100/hour).")

        # Inviter limit: 20/hour
        inv_list = [t for t in self._inviter_timestamps.get(inv_key, []) if t > one_hour_ago]
        if len(inv_list) >= 20:
            raise InvitationRateLimitError("Inviter hourly invitation limit reached (max 20/hour).")

        # Target email limit: 5/day
        email_list = [t for t in self._email_timestamps.get(email_key, []) if t > one_day_ago]
        if len(email_list) >= 5:
            raise InvitationRateLimitError("Daily invitation limit for this recipient email exceeded (max 5/day).")

        # Record timestamps
        ws_list.append(now)
        self._workspace_timestamps[ws_key] = ws_list

        inv_list.append(now)
        self._inviter_timestamps[inv_key] = inv_list

        email_list.append(now)
        self._email_timestamps[email_key] = email_list


_rate_limiter = InvitationRateLimiter()


# ── Invitation Service ────────────────────────────────────────────────────────

class WorkspaceInvitationService:
    """Enterprise domain service for workspace invitations."""

    def __init__(
        self,
        invitation_repo: WorkspaceInvitationRepository,
        member_repo: WorkspaceMemberRepository,
        workspace_repo: WorkspaceRepository,
        settings_repo: WorkspaceSettingsRepository,
        email_provider: EmailProvider,
        event_dispatcher: EventDispatcher | None = None,
        rate_limiter: InvitationRateLimiter | None = None,
    ):
        self.invitation_repo = invitation_repo
        self.member_repo = member_repo
        self.workspace_repo = workspace_repo
        self.settings_repo = settings_repo
        self.email_provider = email_provider
        self.event_dispatcher = event_dispatcher
        self.rate_limiter = rate_limiter or _rate_limiter

    async def _resolve_ttl_days(self, workspace_id: uuid.UUID) -> int:
        """Fetch configured invitation TTL from WorkspaceSettings, clamped [1, 30], defaulting to 7."""
        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        if settings:
            s_dict = getattr(settings, "settings_json", None) or getattr(settings, "settings", None)
            if isinstance(s_dict, dict):
                inv_config = s_dict.get("invitations", {})
                ttl = inv_config.get("ttl_days")
                if isinstance(ttl, int) and 1 <= ttl <= 30:
                    return ttl
        return 7

    async def _verify_actor_permission(
        self, workspace_id: uuid.UUID, actor_id: uuid.UUID, target_role: str
    ) -> WorkspaceMember:
        """Ensure actor is an active OWNER/ADMIN and target role <= actor role."""
        member = await self.member_repo.get_membership(workspace_id, actor_id)
        if not member:
            raise InvitationUnauthorizedError("Actor is not a member of this workspace.")

        actor_role = member.role.upper()
        target_role_upper = target_role.upper()

        if actor_role not in ["OWNER", "ADMIN"]:
            raise InvitationUnauthorizedError("Only workspace OWNER or ADMIN can manage invitations.")

        # Role hierarchy check: ADMIN cannot invite OWNER
        if actor_role == "ADMIN" and target_role_upper == "OWNER":
            raise InvitationUnauthorizedError("ADMIN cannot invite a user to the OWNER role.")

        return member

    async def send_invitation(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        email: str,
        role: str = "MEMBER",
        custom_message: str | None = None,
    ) -> WorkspaceInvitation:
        """
        Creates, persists, and asynchronously dispatches a new workspace invitation.
        """
        email_normalized = email.strip().lower()
        role_upper = role.strip().upper()

        # 1. Validate workspace status
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise InvitationNotFoundError("Workspace not found.")
        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise InvitationInvalidStateError(
                f"Workspace is {workspace.status}. Invitations can only be sent for ACTIVE workspaces."
            )

        # 2. Validate actor permissions & role hierarchy
        await self._verify_actor_permission(workspace_id, actor_id, role_upper)

        # 3. Enforce rate limits
        self.rate_limiter.check_and_record(workspace_id, actor_id, email_normalized)

        # 4. Check if invitee is already an active member
        # Check by email lookup in users table
        user_stmt = select(User).where(User.email == email_normalized, User.is_deleted == False)
        user_res = await session.execute(user_stmt)
        existing_user = user_res.scalars().first()
        if existing_user:
            existing_membership = await self.member_repo.get_membership(workspace_id, existing_user.id)
            if existing_membership:
                raise InvitationConflictError("The user is already a member of this workspace.")

        # 5. Check for active PENDING invitation for this email in this workspace
        existing_pending = await self.invitation_repo.get_pending_by_workspace_and_email(
            workspace_id, email_normalized
        )
        if existing_pending:
            raise InvitationConflictError(
                "A pending invitation already exists for this email in this workspace. Use resend instead."
            )

        # 6. Generate cryptographic token and calculate expiration
        raw_token, token_hash = generate_invitation_token()
        ttl_days = await self._resolve_ttl_days(workspace_id)
        now_utc = datetime.datetime.now(UTC)
        expires_at = now_utc + datetime.timedelta(days=ttl_days)

        # 7. Persist entity
        invitation = WorkspaceInvitation(
            workspace_id=workspace_id,
            email=email_normalized,
            role=role_upper,
            token_hash=token_hash,
            status=InvitationStatus.PENDING.value,
            invited_by_user_id=actor_id,
            expires_at=expires_at,
            resend_count=0,
            version=1,
        )
        session.add(invitation)

        # 8. Record audit log
        audit_log = AuditLog(
            action="workspace.invitation.created",
            user_id=actor_id,
            resource_type="WORKSPACE_INVITATION",
            resource_id=str(invitation.id),
            details={
                "workspace_id": str(workspace_id),
                "target_email": email_normalized,
                "assigned_role": role_upper,
                "expires_at": expires_at.isoformat(),
                "ttl_days": ttl_days,
            },
            status="success",
        )
        session.add(audit_log)

        # Flush to generate ID and commit DB transaction BEFORE dispatching email
        await session.flush()
        await session.commit()

        # 9. Emit domain event
        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceInvitationCreatedEvent(
                    workspace_id=str(workspace_id),
                    invitation_id=str(invitation.id),
                    invited_by_user_id=str(actor_id),
                    email=email_normalized,
                    role=role_upper,
                    expires_at=expires_at.isoformat(),
                    details={"custom_message": custom_message},
                )
            )

        # 10. Asynchronously dispatch invitation email (Failure Policy: Never rollback DB commit)
        try:
            inviter_name = None
            if existing_user:
                inviter_name = existing_user.username or existing_user.email
            await self.email_provider.send_invitation_email(
                to_email=email_normalized,
                raw_token=raw_token,
                workspace_name=workspace.name,
                role=role_upper,
                inviter_name=inviter_name,
                custom_message=custom_message,
                expires_at=expires_at.isoformat(),
            )
        except Exception as ex:
            logger.error(
                "Failed to send invitation email; invitation remains PENDING for resend",
                invitation_id=str(invitation.id),
                error=str(ex),
            )

        return invitation

    async def resend_invitation(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        invitation_id: uuid.UUID,
        actor_id: uuid.UUID,
        custom_message: str | None = None,
    ) -> WorkspaceInvitation:
        """
        Rotates token, extends expiry, and resends invitation email with cooldown & limit checks.
        """
        # 1. Validate workspace status
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise InvitationNotFoundError("Workspace not found.")
        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise InvitationInvalidStateError(
                f"Workspace is {workspace.status}. Cannot resend invitations."
            )

        # 2. Validate actor permissions
        await self._verify_actor_permission(workspace_id, actor_id, "VIEWER")

        # 3. Retrieve invitation
        invitation = await self.invitation_repo.get_by_id(invitation_id, workspace_id)
        if not invitation:
            raise InvitationNotFoundError("Invitation not found in this workspace.")

        if invitation.status != InvitationStatus.PENDING.value:
            raise InvitationInvalidStateError(
                f"Cannot resend invitation in '{invitation.status}' status. Only PENDING invitations can be resent."
            )

        # 4. Check 60-second cooldown
        now_utc = datetime.datetime.now(UTC)
        last_action_time = invitation.last_resent_at or invitation.created_at
        if last_action_time:
            # Handle tz awareness
            if last_action_time.tzinfo is None:
                last_action_time = last_action_time.replace(tzinfo=UTC)
            elapsed = (now_utc - last_action_time).total_seconds()
            if elapsed < 60:
                retry_after = int(60 - elapsed)
                raise InvitationRateLimitError(
                    f"Please wait {retry_after} seconds before resending this invitation."
                )

        # 5. Check maximum resend limit (max 5 resends)
        if invitation.resend_count >= 5:
            raise InvitationRateLimitError(
                "Maximum resend limit (5) reached for this invitation. Please revoke and issue a new one."
            )

        # 6. Generate new token & extend expiry
        raw_token, token_hash = generate_invitation_token()
        ttl_days = await self._resolve_ttl_days(workspace_id)
        expires_at = now_utc + datetime.timedelta(days=ttl_days)

        # 7. Update entity with optimistic concurrency bump
        invitation.token_hash = token_hash
        invitation.expires_at = expires_at
        invitation.resend_count += 1
        invitation.last_resent_at = now_utc
        invitation.version += 1
        session.add(invitation)

        # 8. Record audit log
        audit_log = AuditLog(
            action="workspace.invitation.resent",
            user_id=actor_id,
            resource_type="WORKSPACE_INVITATION",
            resource_id=str(invitation.id),
            details={
                "workspace_id": str(workspace_id),
                "target_email": invitation.email,
                "resend_count": invitation.resend_count,
                "new_expires_at": expires_at.isoformat(),
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        # 9. Emit domain event
        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceInvitationResentEvent(
                    workspace_id=str(workspace_id),
                    invitation_id=str(invitation.id),
                    actor_id=str(actor_id),
                    email=invitation.email,
                    resend_count=invitation.resend_count,
                    expires_at=expires_at.isoformat(),
                )
            )

        # 10. Async email dispatch
        try:
            await self.email_provider.send_invitation_email(
                to_email=invitation.email,
                raw_token=raw_token,
                workspace_name=workspace.name,
                role=invitation.role,
                custom_message=custom_message,
                expires_at=expires_at.isoformat(),
            )
        except Exception as ex:
            logger.error("Failed to resend invitation email", invitation_id=str(invitation.id), error=str(ex))

        return invitation

    async def revoke_invitation(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        invitation_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> WorkspaceInvitation:
        """
        Revokes a pending invitation.
        """
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise InvitationNotFoundError("Workspace not found.")
        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise InvitationInvalidStateError(
                f"Workspace is {workspace.status}. Cannot revoke invitations."
            )

        await self._verify_actor_permission(workspace_id, actor_id, "VIEWER")

        invitation = await self.invitation_repo.get_by_id(invitation_id, workspace_id)
        if not invitation:
            raise InvitationNotFoundError("Invitation not found in this workspace.")

        if invitation.status != InvitationStatus.PENDING.value:
            raise InvitationInvalidStateError(
                f"Cannot revoke invitation in '{invitation.status}' status. Only PENDING invitations can be revoked."
            )

        now_utc = datetime.datetime.now(UTC)
        invitation.status = InvitationStatus.REVOKED.value
        invitation.revoked_at = now_utc
        invitation.revoked_by_user_id = actor_id
        invitation.version += 1
        session.add(invitation)

        audit_log = AuditLog(
            action="workspace.invitation.revoked",
            user_id=actor_id,
            resource_type="WORKSPACE_INVITATION",
            resource_id=str(invitation.id),
            details={
                "workspace_id": str(workspace_id),
                "target_email": invitation.email,
                "revoked_at": now_utc.isoformat(),
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceInvitationRevokedEvent(
                    workspace_id=str(workspace_id),
                    invitation_id=str(invitation.id),
                    actor_id=str(actor_id),
                    email=invitation.email,
                )
            )

        return invitation

    async def verify_invitation_token(
        self,
        session: AsyncSession,
        raw_token: str,
    ) -> dict[str, Any]:
        """
        Verifies raw token for acceptance page preview and logs 'viewed' audit event.
        """
        token_h = hash_token(raw_token)
        invitation = await self.invitation_repo.get_by_token_hash(token_h)
        if not invitation:
            raise InvitationNotFoundError("Invalid or expired invitation token.")

        now_utc = datetime.datetime.now(UTC)
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        # Lazy expiration check
        if expires_at < now_utc and invitation.status == InvitationStatus.PENDING.value:
            invitation.status = InvitationStatus.EXPIRED.value
            invitation.version += 1
            session.add(invitation)
            await session.flush()
            await session.commit()
            raise InvitationInvalidStateError("This invitation has expired.")

        if invitation.status != InvitationStatus.PENDING.value:
            raise InvitationInvalidStateError(f"This invitation is no longer valid ({invitation.status}).")

        workspace_name = invitation.workspace.name if invitation.workspace else "Workspace"
        inviter_email = invitation.invited_by.email if invitation.invited_by else None

        # Record viewed audit log
        audit_log = AuditLog(
            action="workspace.invitation.viewed",
            user_id=invitation.invited_by_user_id,
            resource_type="WORKSPACE_INVITATION",
            resource_id=str(invitation.id),
            details={
                "workspace_id": str(invitation.workspace_id),
                "target_email": invitation.email,
            },
            status="success",
        )
        session.add(audit_log)
        await session.flush()
        await session.commit()

        return {
            "invitation_id": invitation.id,
            "workspace_id": invitation.workspace_id,
            "workspace_name": workspace_name,
            "email": invitation.email,
            "role": invitation.role,
            "inviter_email": inviter_email,
            "expires_at": invitation.expires_at,
            "status": invitation.status,
        }

    async def accept_invitation(
        self,
        session: AsyncSession,
        raw_token: str,
        user_context: Any,
    ) -> dict[str, Any]:
        """
        Accepts a pending workspace invitation atomically under row lock (F4.2).
        """
        if not raw_token or not raw_token.strip():
            raise InvitationError("Invitation token is required.")

        token_h = hash_token(raw_token)
        now_utc = datetime.datetime.now(UTC)

        # 1. Pessimistic row-level locking
        invitation = await self.invitation_repo.get_by_token_hash_for_update(token_h)
        if not invitation:
            # Audit failure
            audit_log = AuditLog(
                action="workspace.invitation.accept_failed",
                user_id=getattr(user_context, "id", None),
                resource_type="WORKSPACE_INVITATION",
                resource_id=token_h[:12],
                details={"reason": "Invalid token or invitation not found"},
                status="failure",
            )
            session.add(audit_log)
            await session.flush()
            await session.commit()
            raise InvitationNotFoundError("Invalid or non-existent invitation token.")

        workspace_id = invitation.workspace_id

        # 2. Check if workspace is ACTIVE
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise InvitationInvalidStateError("Cannot accept invitation for an inactive or archived workspace.")

        # 3. Check expiration
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now_utc:
            if invitation.status == InvitationStatus.PENDING.value:
                invitation.status = InvitationStatus.EXPIRED.value
                invitation.version += 1
                session.add(invitation)

            audit_log = AuditLog(
                action="workspace.invitation.accept_failed",
                user_id=user_context.id,
                resource_type="WORKSPACE_INVITATION",
                resource_id=str(invitation.id),
                details={
                    "workspace_id": str(workspace_id),
                    "reason": "Invitation expired",
                    "expires_at": expires_at.isoformat(),
                },
                status="failure",
            )
            session.add(audit_log)
            await session.flush()
            await session.commit()
            raise InvitationInvalidStateError("This invitation has expired.")

        # 4. Check invitation status is PENDING
        if invitation.status != InvitationStatus.PENDING.value:
            audit_log = AuditLog(
                action="workspace.invitation.accept_failed",
                user_id=user_context.id,
                resource_type="WORKSPACE_INVITATION",
                resource_id=str(invitation.id),
                details={
                    "workspace_id": str(workspace_id),
                    "reason": f"Invalid invitation status: {invitation.status}",
                },
                status="failure",
            )
            session.add(audit_log)
            await session.flush()
            await session.commit()
            raise InvitationInvalidStateError(f"Invitation is already {invitation.status}.")

        # 5. Email Normalization & Ownership validation
        user_email = user_context.email.strip().lower()
        invite_email = invitation.email.strip().lower()
        if user_email != invite_email:
            audit_log = AuditLog(
                action="workspace.invitation.accept_failed",
                user_id=user_context.id,
                resource_type="WORKSPACE_INVITATION",
                resource_id=str(invitation.id),
                details={
                    "workspace_id": str(workspace_id),
                    "reason": "Email mismatch",
                    "user_email": user_email,
                    "target_email": invite_email,
                },
                status="failure",
            )
            session.add(audit_log)
            await session.flush()
            await session.commit()
            raise InvitationUnauthorizedError(
                "Logged in user email does not match the invitation recipient."
            )

        # 6. Existing membership check
        existing_member = await self.member_repo.get_membership(workspace_id, user_context.id)
        if existing_member:
            invitation.status = InvitationStatus.ACCEPTED.value
            invitation.accepted_at = now_utc
            invitation.version += 1
            session.add(invitation)
            await session.flush()
            await session.commit()
            raise InvitationConflictError("You are already a member of this workspace.")

        # 7. Atomic state transition & Member creation
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = now_utc
        invitation.version += 1
        session.add(invitation)

        from backend.models.entities.workspace_member import MemberStatus
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_context.id,
            role=invitation.role,
            status=MemberStatus.ACTIVE.value,
            invited_by_user_id=invitation.invited_by_user_id,
            joined_at=now_utc,
            version=1,
        )
        session.add(member)

        # 8. Record audit log
        audit_log = AuditLog(
            action="workspace.invitation.accepted",
            user_id=user_context.id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(workspace_id),
                "invitation_id": str(invitation.id),
                "role": invitation.role,
                "email": invite_email,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        # 9. Emit domain event
        if self.event_dispatcher:
            await self.event_dispatcher.publish(
                WorkspaceInvitationAcceptedEvent(
                    workspace_id=str(workspace_id),
                    invitation_id=str(invitation.id),
                    member_id=str(member.id),
                    user_id=str(user_context.id),
                    email=invite_email,
                    role=invitation.role,
                )
            )

        return {
            "success": True,
            "workspace_id": workspace_id,
            "workspace_name": workspace.name,
            "role": invitation.role,
            "member_id": member.id,
        }

    async def list_invitations(
        self,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkspaceInvitation], int]:
        """List paginated workspace invitations for an authorized admin."""
        await self._verify_actor_permission(workspace_id, actor_id, "VIEWER")
        return await self.invitation_repo.list_by_workspace(
            workspace_id=workspace_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def run_expiration_cleanup(self, session: AsyncSession) -> int:
        """Hourly background worker logic: batch marks expired PENDING invitations as EXPIRED."""
        now_utc = datetime.datetime.now(UTC)
        stale_records = await self.invitation_repo.find_expired_pending(now_utc)
        if not stale_records:
            return 0

        expired_ids = [r.id for r in stale_records]
        count = await self.invitation_repo.batch_expire(expired_ids, now_utc)

        for inv in stale_records:
            audit_log = AuditLog(
                action="workspace.invitation.expired",
                user_id=None,
                resource_type="WORKSPACE_INVITATION",
                resource_id=str(inv.id),
                details={
                    "workspace_id": str(inv.workspace_id),
                    "target_email": inv.email,
                    "expired_at": now_utc.isoformat(),
                },
                status="success",
            )
            session.add(audit_log)

            if self.event_dispatcher:
                await self.event_dispatcher.publish(
                    WorkspaceInvitationExpiredEvent(
                        workspace_id=str(inv.workspace_id),
                        invitation_id=str(inv.id),
                        email=inv.email,
                    )
                )

        cleanup_audit = AuditLog(
            action="workspace.invitation.cleanup_worker",
            user_id=None,
            resource_type="SYSTEM",
            resource_id="invitation_expiration_worker",
            details={
                "records_processed": len(stale_records),
                "records_expired": count,
                "timestamp": now_utc.isoformat(),
            },
            status="success",
        )
        session.add(cleanup_audit)
        await session.flush()
        await session.commit()

        logger.info(
            "Completed workspace invitation expiration cleanup",
            records_expired=count,
        )
        return count
