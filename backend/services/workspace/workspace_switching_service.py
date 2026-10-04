"""Workspace Switching Service.

Implements authoritative multi-membership active workspace context switching.
Validates membership server-side, derives authoritative role from target membership,
rotates JWT and refresh sessions, revokes old access token, updates user active context,
and produces audit log entries.
"""

from datetime import UTC, datetime, timedelta
import hashlib
import re
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_onboarding import (
    SwitchWorkspaceData,
    TENANT_UUID_PATTERN,
)
from backend.core.security.jwt import JWTService
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.user_session import UserSession
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository

logger = structlog.get_logger(__name__)


class WorkspaceSwitchError(Exception):
    """Base exception for workspace context switching operations."""


class WorkspaceSwitchNotFoundError(WorkspaceSwitchError):
    """Target workspace not found or not in active state."""


class WorkspaceSwitchForbiddenError(WorkspaceSwitchError):
    """User is not an active member of the target workspace or membership suspended."""


class WorkspaceSwitchInvalidIdentifierError(WorkspaceSwitchError):
    """Target workspace identifier is malformed or invalid."""


class WorkspaceSwitchingService:
    """Authoritative service for switching active workspace session context."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        member_repo: WorkspaceMemberRepository,
        jwt_service: JWTService,
    ) -> None:
        self.workspace_repo = workspace_repo
        self.member_repo = member_repo
        self.jwt_service = jwt_service

    async def resolve_target_workspace(
        self,
        identifier: str | uuid.UUID,
    ) -> Workspace:
        """Resolves target workspace by UUID, Public ID (WS-XXXXXX), or slug."""
        clean = str(identifier).strip()
        if not clean:
            raise WorkspaceSwitchInvalidIdentifierError("Workspace identifier cannot be empty.")

        ws: Workspace | None = None

        # 1. Try parsing as internal Tenant UUID
        try:
            target_uuid = uuid.UUID(clean)
            ws = await self.workspace_repo.get_by_id(target_uuid)
        except (ValueError, TypeError):
            pass

        # 2. Try public Workspace ID (uppercase)
        if not ws:
            ws = await self.workspace_repo.get_by_public_id(clean.upper())

        # 3. Try slug (lowercase)
        if not ws:
            ws = await self.workspace_repo.get_by_slug(clean.lower())

        if not ws or ws.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceSwitchNotFoundError("Workspace not found or access denied.")

        return ws

    async def switch_workspace(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        workspace_identifier: str | uuid.UUID,
        current_jti: str | None = None,
        current_exp: int | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
        device: str | None = None,
    ) -> tuple[SwitchWorkspaceData, str]:
        """Executes authoritative workspace switch for authenticated user.

        Security Invariants:
        1. Membership verified server-side in workspace_members (is_deleted=False, status=ACTIVE).
        2. Non-members or suspended members receive strict 403 denial.
        3. Authoritative role derived strictly from target WorkspaceMember.role (client role never trusted).
        4. Old access token JTI revoked in Redis blocklist if JTI provided.
        5. User.tenant_id updated to target workspace in DB for persistent refresh continuity.
        6. Fresh JWT issued with target workspace_id and role.
        7. Rotated refresh token issued and session persisted.
        8. Comprehensive audit log emitted.

        Returns:
            Tuple of (SwitchWorkspaceData, raw_refresh_token).
        """
        # 1. Resolve target workspace
        ws = await self.resolve_target_workspace(workspace_identifier)

        # 2. Authoritative membership verification
        membership = await self.member_repo.get_membership(ws.id, user_id, include_suspended=True)
        if not membership or getattr(membership, "is_deleted", False):
            raise WorkspaceSwitchForbiddenError("You are not a member of this workspace.")

        if membership.status != MemberStatus.ACTIVE.value:
            raise WorkspaceSwitchForbiddenError("Workspace membership is suspended.")

        # 3. Derive authoritative role directly from membership
        target_role = membership.role

        # 4. Invalidate old access token if JTI and expiration provided
        if current_jti and current_exp:
            await self.jwt_service.revoke_token(current_jti, current_exp)

        # 5. Update user's active workspace in DB
        user = await session.get(User, user_id)
        if not user or not user.is_active:
            raise WorkspaceSwitchForbiddenError("User account is inactive or disabled.")

        from_workspace_id = user.tenant_id
        user.tenant_id = str(ws.id)
        user.workspace_name = ws.name
        membership.last_active_at = datetime.now(UTC)

        # 6. Issue fresh tokens scoped to target workspace and role
        access_token, raw_refresh_token, family_id = await self.jwt_service.issue_tokens(
            user=user,
            session=session,
            workspace_id=ws.id,
            role=target_role,
        )

        # 7. Record new rotated UserSession for refresh token
        refresh_token_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()
        session_expires_at = datetime.now(UTC) + timedelta(days=7)
        user_session = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            family_id=family_id,
            expires_at=session_expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            device=device,
            last_used_at=datetime.now(UTC),
        )
        session.add(user_session)

        # 8. Audit logging
        audit_log = AuditLog(
            tenant_id=ws.id,
            action="workspace.context.switched",
            user_id=user_id,
            resource_type="WORKSPACE",
            resource_id=str(ws.id),
            details={
                "from_workspace_id": from_workspace_id,
                "to_workspace_id": str(ws.id),
                "workspace_public_id": ws.public_id,
                "role": target_role,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()

        logger.info(
            "User switched active workspace successfully",
            user_id=str(user_id),
            from_workspace=from_workspace_id,
            to_workspace=str(ws.id),
            role=target_role,
        )

        data = SwitchWorkspaceData(
            workspace_id=ws.id,
            workspace_public_id=ws.public_id,
            workspace_slug=ws.slug,
            workspace_name=ws.name,
            role=target_role,
            access_token=access_token,
            token_type="Bearer",
        )

        return data, raw_refresh_token
