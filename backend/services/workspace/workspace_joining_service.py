"""Workspace Joining Service (WS-A5).

Authoritative join execution across all 3 supported joining modes:
- Mode 1: Open Workspace ID (public_id or slug)
- Mode 2: Protected Workspace ID + Join Code (VR-XXXXXX)
- Mode 3: Invitation Token (sec_inv_*)

SECURITY INVARIANTS:
1. Rejects internal Tenant UUID as a public join credential.
2. Constant-time / slow bcrypt verification for Join Codes.
3. Selector + Verifier cryptographic token verification with email binding check for Invitations.
4. Atomically creates active workspace membership under database lock.
5. Emits audit logs with zero secret leakage (never logs join code or raw invitation token).
6. Prevents cross-workspace leakage (invitation workspace ID must match target workspace ID if both provided).
"""

from datetime import UTC, datetime
import re
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_onboarding import (
    CROCKFORD_ALPHABET,
    INVITATION_TOKEN_PATTERN,
    JOIN_CODE_PATTERN,
    TENANT_UUID_PATTERN,
    JoinWorkspaceData,
)
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationError,
    InvitationInvalidStateError,
    InvitationNotFoundError,
    WorkspaceInvitationService,
)
from backend.services.workspace.join_code_service import JoinCodeService

logger = structlog.get_logger(__name__)


class WorkspaceJoiningError(Exception):
    """Base error for workspace joining operations."""
    pass


class WorkspaceIdentifierInvalidError(WorkspaceJoiningError):
    """Raised when the target workspace identifier is invalid or is a tenant UUID."""
    pass


class WorkspaceTargetNotFoundError(WorkspaceJoiningError):
    """Raised when the target workspace cannot be resolved or is not ACTIVE."""
    pass


class WorkspaceMembershipConflictError(WorkspaceJoiningError):
    """Raised when user is already an active member of the workspace."""
    pass


class WorkspaceMembershipSuspendedError(WorkspaceMembershipConflictError):
    """Raised when an existing suspended member attempts join-code redemption or open join."""
    pass


class WorkspaceJoinIntentMismatchError(WorkspaceJoiningError):
    """Raised when invitation token workspace does not match the target workspace ID."""
    pass


class WorkspaceJoinForbiddenError(WorkspaceJoiningError):
    """Raised when open join is not permitted on this workspace."""
    pass


class WorkspaceJoinCodeInvalidError(WorkspaceJoiningError):
    """Raised when join code candidate validation fails (expired, invalid, or limit reached)."""
    pass


class WorkspaceInvitationJoinError(WorkspaceJoiningError):
    """Raised when invitation token validation or acceptance fails."""
    pass


class _UserContextWrapper:
    """Internal lightweight user context for invitation service interop."""
    def __init__(self, user_id: uuid.UUID, email: str):
        self.id = user_id
        self.email = email


class WorkspaceJoiningService:
    """Coordinates authoritative workspace joining for authenticated users."""

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        settings_repo: WorkspaceSettingsRepository,
        member_repo: WorkspaceMemberRepository,
        join_code_service: JoinCodeService,
        invitation_service: WorkspaceInvitationService,
    ) -> None:
        self.workspace_repo = workspace_repo
        self.settings_repo = settings_repo
        self.member_repo = member_repo
        self.join_code_service = join_code_service
        self.invitation_service = invitation_service

    async def _resolve_workspace(self, identifier: str) -> Any:
        """Resolves active workspace by public_id or slug, rejecting tenant UUID."""
        clean = identifier.strip()
        if re.match(TENANT_UUID_PATTERN, clean):
            raise WorkspaceIdentifierInvalidError(
                "Tenant UUID cannot be used as a public join credential. Use Workspace ID or slug."
            )

        # 1. Try public ID (uppercase)
        ws = await self.workspace_repo.get_by_public_id(clean.upper())
        if not ws:
            # 2. Try slug (lowercase)
            ws = await self.workspace_repo.get_by_slug(clean.lower())

        if not ws or ws.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceTargetNotFoundError(f"Active workspace '{identifier}' not found.")

        return ws

    async def join_workspace(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        user_email: str,
        workspace_identifier: str | None = None,
        join_code: str | None = None,
        invitation_token: str | None = None,
    ) -> JoinWorkspaceData:
        """Executes authoritative join for user across Mode 1, Mode 2, or Mode 3."""
        clean_invitation = invitation_token.strip() if invitation_token else None
        clean_code = join_code.strip().upper() if join_code else None
        clean_identifier = workspace_identifier.strip() if workspace_identifier else None

        # Mode 3: Invitation Token
        if clean_invitation:
            return await self._join_via_invitation(
                session=session,
                user_id=user_id,
                user_email=user_email,
                invitation_token=clean_invitation,
                workspace_identifier=clean_identifier,
            )

        # Mode 2: Protected Join Code
        if clean_code:
            if not clean_identifier:
                raise WorkspaceIdentifierInvalidError(
                    "Workspace identifier (Workspace ID or Slug) is required when joining with a Join Code."
                )
            return await self._join_via_code(
                session=session,
                user_id=user_id,
                user_email=user_email,
                workspace_identifier=clean_identifier,
                join_code=clean_code,
            )

        # Mode 1: Open Workspace ID
        if clean_identifier:
            return await self._join_via_open(
                session=session,
                user_id=user_id,
                user_email=user_email,
                workspace_identifier=clean_identifier,
            )

        raise WorkspaceIdentifierInvalidError(
            "Either workspace_identifier or invitation_token must be provided to join a workspace."
        )

    async def _join_via_invitation(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        user_email: str,
        invitation_token: str,
        workspace_identifier: str | None = None,
    ) -> JoinWorkspaceData:
        """Mode 3: Join via cryptographically verified invitation token."""
        target_ws = None
        if workspace_identifier:
            target_ws = await self._resolve_workspace(workspace_identifier)

        wrapper_context = _UserContextWrapper(user_id=user_id, email=user_email)

        try:
            accept_result = await self.invitation_service.accept_invitation(
                session=session,
                raw_token=invitation_token,
                user_context=wrapper_context,
            )
        except InvitationConflictError as e:
            raise WorkspaceMembershipConflictError("User is already a member of this workspace.") from e
        except (InvitationNotFoundError, InvitationInvalidStateError, InvitationError) as e:
            raise WorkspaceInvitationJoinError(str(e)) from e

        ws_id = accept_result["workspace_id"]
        if target_ws and target_ws.id != ws_id:
            raise WorkspaceJoinIntentMismatchError(
                "Invitation token belongs to a different workspace than the target identifier specified."
            )

        member = await self.member_repo.get_membership(ws_id, user_id)
        member_id = member.id if member else uuid.uuid4()

        logger.info(
            "User successfully joined workspace via invitation token",
            workspace_id=str(ws_id),
            user_id=str(user_id),
            role=accept_result["role"],
        )

        return JoinWorkspaceData(
            workspace_id=ws_id,
            workspace_name=accept_result["workspace_name"],
            role=accept_result["role"],
            status="ACTIVE",
            member_id=member_id,
        )

    async def _join_via_code(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        user_email: str,
        workspace_identifier: str,
        join_code: str,
    ) -> JoinWorkspaceData:
        """Mode 2: Join via protected Workspace ID + Join Code."""
        # Lifecycle Admission Control (T3C-DEC-3): User FOR SHARE
        from backend.core.security.admission import validate_user_admission_for_share, UserAdmissionDeniedError
        try:
            await validate_user_admission_for_share(session, user_id)
        except UserAdmissionDeniedError as e:
            raise WorkspaceMembershipConflictError(
                "Unable to join workspace. User account is inactive, deleted, or deactivating."
            ) from e

        ws = await self._resolve_workspace(workspace_identifier)

        # Check existing membership state (never silently reactivate or overwrite stored role)
        try:
            existing = await self.member_repo.get_membership(
                ws.id, user_id, include_suspended=True, include_deleted=True
            )
        except TypeError:
            existing = await self.member_repo.get_membership(ws.id, user_id)

        if existing:
            if existing.status == MemberStatus.ACTIVE.value and not getattr(existing, "is_deleted", False):
                raise WorkspaceMembershipConflictError("User is already an active member of this workspace.")
            if existing.status == MemberStatus.SUSPENDED.value:
                raise WorkspaceMembershipSuspendedError(
                    "Unable to join workspace. Account status does not permit join-code redemption. Contact your workspace administrator."
                )
            if getattr(existing, "is_deleted", False):
                raise WorkspaceMembershipConflictError(
                    "Unable to join workspace. Account status does not permit join-code redemption. Contact your workspace administrator."
                )
            raise WorkspaceMembershipConflictError(
                "Unable to join workspace. Existing membership status does not permit joining with this code."
            )

        # Cryptographically validate candidate code against stored verifier
        validation_res = await self.join_code_service.validate_join_code_candidate(
            session=session,
            workspace_id=ws.id,
            candidate_code=join_code,
            return_record=True,
        )
        code_record = None
        if isinstance(validation_res, (list, tuple)) and len(validation_res) == 4:
            is_valid, err_reason, default_role, code_record = validation_res
        else:
            is_valid, err_reason, default_role = validation_res

        if not is_valid:
            raise WorkspaceJoinCodeInvalidError(err_reason or "Invalid join code.")

        candidate_code_id = code_record.id if code_record else None
        creator_id = code_record.created_by_user_id if code_record else None

        # Post-lock creator eligibility revalidation
        if creator_id:
            from backend.models.entities.user import User
            creator_user = await session.get(User, creator_id)
            if not creator_user or not creator_user.is_active or creator_user.is_deleted:
                raise WorkspaceJoinCodeInvalidError("Join code creator is no longer active.")
            creator_member = await self.member_repo.get_membership(ws.id, creator_id)
            if (
                not creator_member
                or creator_member.status != MemberStatus.ACTIVE.value
                or creator_member.is_deleted
                or (creator_member.role and creator_member.role.upper() not in ("OWNER", "ADMIN"))
            ):
                raise WorkspaceJoinCodeInvalidError("Join code creator is no longer an eligible administrator.")
            # Locked Creator Identity Consistency (Section 13.3)
            if code_record.created_by_user_id != creator_id:
                raise WorkspaceJoinCodeInvalidError("Creator identity mutated in-flight; admission aborted.")

        # Enforce role ceiling: join-code self-service default role is strictly capped at MEMBER
        sanitized_role = default_role.upper() if default_role else "MEMBER"
        if sanitized_role not in ("MEMBER",):
            logger.warning(
                "Attempted join-code redemption with elevated default role; capping at MEMBER",
                configured_role=default_role,
                workspace_id=str(ws.id),
                user_id=str(user_id),
            )
            sanitized_role = "MEMBER"

        # Check workspace join code policy for require_approval
        ws_settings = await self.settings_repo.get_by_workspace_id(ws.id)
        require_approval = False
        if ws_settings and hasattr(ws_settings, "settings_json") and isinstance(ws_settings.settings_json, dict):
            require_approval = bool(ws_settings.settings_json.get("join_code_require_approval", False))
        elif ws_settings and isinstance(getattr(ws_settings, "join_code_require_approval", None), bool):
            require_approval = bool(ws_settings.join_code_require_approval)

        if require_approval:
            from backend.models.entities.workspace_access_request import (
                AccessRequestStatus,
                AccessRequestType,
                WorkspaceAccessRequest,
            )
            from backend.repositories.workspace_access_request import WorkspaceAccessRequestRepository

            access_repo = WorkspaceAccessRequestRepository(session)
            pending_req = await access_repo.get_active_pending(
                ws.id, user_id, AccessRequestType.JOIN_APPROVAL.value
            )
            if pending_req:
                raise WorkspaceMembershipConflictError(
                    "Your join request is currently pending administrator approval."
                )

            join_req = WorkspaceAccessRequest(
                workspace_id=ws.id,
                user_id=user_id,
                request_type=AccessRequestType.JOIN_APPROVAL.value,
                current_role=None,
                requested_role=sanitized_role,
                status=AccessRequestStatus.PENDING.value,
                reason="Joined via Join Code (requires administrator approval)",
            )
            session.add(join_req)
            await session.flush()

            # Record audit log
            audit_log = AuditLog(
                tenant_id=ws.id,
                action="workspace.access_request.created",
                user_id=user_id,
                resource_type="WORKSPACE_ACCESS_REQUEST",
                resource_id=str(join_req.id),
                details={
                    "workspace_id": str(ws.id),
                    "request_type": "JOIN_APPROVAL",
                    "role": sanitized_role,
                    "joining_mode": "JOIN_CODE",
                },
                status="success",
            )
            session.add(audit_log)
            await session.flush()
            await session.commit()

            logger.info(
                "User submitted join approval request via Join Code",
                workspace_id=str(ws.id),
                user_id=str(user_id),
                role=sanitized_role,
            )

            return JoinWorkspaceData(
                workspace_id=ws.id,
                workspace_name=ws.name,
                role=sanitized_role,
                status="PENDING_APPROVAL",
                member_id=uuid.uuid4(),
            )

        # Create brand-new membership record (never mutate an existing record)
        now_utc = datetime.now(UTC)
        attribution_snapshot = {
            "origin": "join_code",
            "creator_user_id": str(creator_id) if creator_id else None,
            "join_code_id": str(candidate_code_id) if candidate_code_id else None,
            "redeemed_at": now_utc.isoformat(),
        }
        member_meta = {"attribution_snapshot": attribution_snapshot}

        member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            user_id=user_id,
            role=sanitized_role,
            status=MemberStatus.ACTIVE.value,
            invited_by_user_id=creator_id,
            member_metadata=member_meta,
            version=1,
        )
        session.add(member)
        await session.flush()

        # Insert redemption ledger record if code_id exists
        if candidate_code_id:
            from backend.models.entities.workspace_join_code import WorkspaceJoinCodeRedemption
            redemption = WorkspaceJoinCodeRedemption(
                id=uuid.uuid4(),
                join_code_id=candidate_code_id,
                workspace_id=ws.id,
                user_id=user_id,
                redeemed_at=now_utc,
            )
            session.add(redemption)
            await session.flush()

        # Increment usage counter with actual code_id
        if candidate_code_id is not None:
            await self.join_code_service.record_join_code_usage(session, ws.id, code_id=candidate_code_id)
        else:
            await self.join_code_service.record_join_code_usage(session, ws.id)

        # Audit log with zero secret leakage
        audit_log = AuditLog(
            tenant_id=ws.id,
            action="workspace.member.joined_via_code",
            user_id=user_id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(ws.id),
                "role": sanitized_role,
                "joining_mode": "JOIN_CODE",
            },
            status="success",
        )
        session.add(audit_log)
        await session.flush()
        await session.commit()

        logger.info(
            "User successfully joined workspace via Join Code",
            workspace_id=str(ws.id),
            user_id=str(user_id),
            role=sanitized_role,
        )

        return JoinWorkspaceData(
            workspace_id=ws.id,
            workspace_name=ws.name,
            role=sanitized_role,
            status="ACTIVE",
            member_id=member.id,
        )

    async def _join_via_open(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        user_email: str,
        workspace_identifier: str,
    ) -> JoinWorkspaceData:
        """Mode 1: Join via open Workspace ID (open_join=True)."""
        # Lifecycle Admission Control (T3C-DEC-3): User FOR SHARE
        from backend.core.security.admission import validate_user_admission_for_share, UserAdmissionDeniedError
        try:
            await validate_user_admission_for_share(session, user_id)
        except UserAdmissionDeniedError as e:
            raise WorkspaceMembershipConflictError(
                "Unable to join workspace. User account is inactive, deleted, or deactivating."
            ) from e

        ws = await self._resolve_workspace(workspace_identifier)

        settings = await self.settings_repo.get_by_workspace_id(ws.id)
        open_join = False
        default_role = "MEMBER"
        if settings and settings.settings_json:
            open_join = bool(settings.settings_json.get("open_join", False))
            default_role = settings.settings_json.get("default_join_role", "MEMBER")

        if not open_join:
            raise WorkspaceJoinForbiddenError(
                "This workspace does not permit open self-service joining. A valid Join Code or invitation is required."
            )

        # Check existing membership state (never silently reactivate or overwrite stored role)
        try:
            existing = await self.member_repo.get_membership(
                ws.id, user_id, include_suspended=True, include_deleted=True
            )
        except TypeError:
            existing = await self.member_repo.get_membership(ws.id, user_id)

        if existing:
            if existing.status == MemberStatus.ACTIVE.value and not getattr(existing, "is_deleted", False):
                raise WorkspaceMembershipConflictError("User is already an active member of this workspace.")
            if existing.status == MemberStatus.SUSPENDED.value:
                raise WorkspaceMembershipSuspendedError(
                    "Unable to join workspace. Account status does not permit open joining. Contact your workspace administrator."
                )
            if getattr(existing, "is_deleted", False):
                raise WorkspaceMembershipConflictError(
                    "Unable to join workspace. Account status does not permit open joining. Contact your workspace administrator."
                )
            raise WorkspaceMembershipConflictError(
                "Unable to join workspace. Existing membership status does not permit joining."
            )

        # Enforce role ceiling: open self-service join default role is strictly capped at MEMBER
        sanitized_role = default_role.upper() if default_role else "MEMBER"
        if sanitized_role not in ("MEMBER",):
            logger.warning(
                "Attempted open join with elevated default role; capping at MEMBER",
                configured_role=default_role,
                workspace_id=str(ws.id),
                user_id=str(user_id),
            )
            sanitized_role = "MEMBER"

        member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            user_id=user_id,
            role=sanitized_role,
            status=MemberStatus.ACTIVE.value,
            version=1,
        )
        session.add(member)
        await session.flush()

        audit_log = AuditLog(
            tenant_id=ws.id,
            action="workspace.member.joined_open",
            user_id=user_id,
            resource_type="WORKSPACE_MEMBER",
            resource_id=str(member.id),
            details={
                "workspace_id": str(ws.id),
                "role": sanitized_role,
                "joining_mode": "OPEN",
            },
            status="success",
        )
        session.add(audit_log)
        await session.flush()
        await session.commit()

        logger.info(
            "User successfully joined workspace via open join policy",
            workspace_id=str(ws.id),
            user_id=str(user_id),
            role=sanitized_role,
        )

        return JoinWorkspaceData(
            workspace_id=ws.id,
            workspace_name=ws.name,
            role=sanitized_role,
            status="ACTIVE",
            member_id=member.id,
        )
