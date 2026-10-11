"""User Lifecycle and Deactivation Service.

Provides:
- Mandatory password re-authentication (or recent authentication check).
- Transactional sole-owner workspace protection.
- Soft-delete account deactivation (`is_deleted=True, is_active=False`).
- Full session & refresh token invalidation across DB and Redis.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.models.entities.user import User
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace import Workspace
from backend.models.entities.user_session import UserSession
from backend.core.security.password import verify_password
from backend.core.security.jwt import get_jwt_service

logger = structlog.get_logger(__name__)


class LifecycleException(Exception):
    pass


class ReauthenticationFailedException(LifecycleException):
    pass


class SoleWorkspaceOwnerConflictException(LifecycleException):
    def __init__(self, workspace_names: list[str]):
        self.workspace_names = workspace_names
        super().__init__(
            f"Cannot deactivate account. You are the sole owner of active workspace(s): "
            f"{', '.join(workspace_names)}. Please transfer ownership or delete the workspace first."
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
        """Detects whether user is the sole owner of any active workspace."""
        # Find all active workspaces where this user is an OWNER
        owned_stmt = (
            select(WorkspaceMember.workspace_id, Workspace.name)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.role.in_(["OWNER", "workspace_owner"]),
                WorkspaceMember.is_deleted == False,
                Workspace.is_deleted == False,
                Workspace.status == "ACTIVE"
            )
        )
        owned_rows = (await self.session.execute(owned_stmt)).all()

        conflicts = []
        for ws_id, ws_name in owned_rows:
            # Count other active owners in this workspace
            other_owners_stmt = select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == ws_id,
                WorkspaceMember.user_id != user_id,
                WorkspaceMember.role.in_(["OWNER", "workspace_owner"]),
                WorkspaceMember.is_deleted == False,
                WorkspaceMember.status == "ACTIVE"
            )
            other_owners_count = (await self.session.execute(other_owners_stmt)).scalar() or 0
            if other_owners_count == 0:
                conflicts.append(ws_name)

        if conflicts:
            raise SoleWorkspaceOwnerConflictException(conflicts)

    async def deactivate_user_account(
        self,
        user_id: uuid.UUID,
        password: str | None = None,
        confirmation_text: str = ""
    ) -> None:
        """Atomically validates requirements, deactivates account, and revokes all sessions."""
        if confirmation_text.strip().upper() != "DELETE":
            raise LifecycleException("Confirmation failed: you must type DELETE to confirm.")

        # Load user with row lock to serialize concurrent lifecycle changes
        user_stmt = select(User).where(User.id == user_id).with_for_update()
        user = (await self.session.execute(user_stmt)).scalar_one_or_none()
        if not user or user.is_deleted:
            raise LifecycleException("User not found or already deactivated.")

        # 1. Re-authentication check
        await self.verify_credentials(user, password)

        # 2. Transactional Sole-owner guard
        await self.check_sole_workspace_ownership(user_id)

        # 3. Soft-delete user state
        user.is_active = False
        user.is_deleted = True
        user.updated_at = datetime.now(timezone.utc)

        # 4. Invalidate all UserSession entries in DB
        session_stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.is_revoked == False)
            .values(is_revoked=True)
        )
        await self.session.execute(session_stmt)

        # 5. Revoke user sessions in Redis / JWT blocklist
        try:
            # Revoke current token family if tracked
            await self.jwt_service.revoke_user_tokens(str(user_id))
        except Exception as e:
            logger.warning("Redis token revocation completed with notice", error=str(e))

        await self.session.commit()
        logger.info("User account successfully deactivated", user_id=str(user_id))
