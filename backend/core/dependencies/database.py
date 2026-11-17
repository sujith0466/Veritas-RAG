"""FastAPI database and repository dependency providers.

Yields request-scoped database sessions, Redis/Qdrant clients, and repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Depends, Request

from backend.cache.client import get_cache as _get_cache
from backend.database.engine import get_async_session
from backend.repositories import (
    AuditLogRepository,
    IAuditLogRepository,
    IUserRepository,
    UserRepository,
)
from backend.vector_db.client import get_vector_db as _get_vector_db

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from qdrant_client import AsyncQdrantClient
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an isolated async database session per request."""
    async for session in get_async_session():
        yield session


async def get_cache() -> AsyncGenerator[Redis[Any], None]:
    """Yield an async Redis client instance per request."""
    async for client in _get_cache():
        yield client


async def get_vector_db() -> AsyncGenerator[AsyncQdrantClient, None]:
    """Yield an async Qdrant client instance per request."""
    async for client in _get_vector_db():
        yield client


async def get_sso_service(
    session: AsyncSession = Depends(get_db),
):
    from backend.services.sso_service import SSOService

    return SSOService(session=session)


async def get_folder_service(
    session: AsyncSession = Depends(get_db),
):
    from backend.core.events.dispatcher import EventDispatcher
    from backend.services.folder_service import FolderService

    return FolderService(session=session, dispatcher=EventDispatcher())


async def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> IUserRepository:
    """FastAPI dependency yielding a UserRepository instance."""
    return UserRepository(session)


async def get_audit_log_repository(
    session: AsyncSession = Depends(get_db),
) -> IAuditLogRepository:
    """FastAPI dependency yielding an AuditLogRepository instance."""
    return AuditLogRepository(session)


# Workspace Dependencies

from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.repositories.workspace_settings_history import WorkspaceSettingsHistoryRepository
from backend.services.workspace.management_service import WorkspaceManagementService
from backend.services.workspace.provisioning_service import WorkspaceProvisioningService
from backend.services.workspace.settings_service import WorkspaceSettingsService


async def get_workspace_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceRepository:
    return WorkspaceRepository(session)

async def get_workspace_settings_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceSettingsRepository:
    return WorkspaceSettingsRepository(session)

async def get_workspace_settings_history_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceSettingsHistoryRepository:
    return WorkspaceSettingsHistoryRepository(session)

async def get_workspace_member_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceMemberRepository:
    return WorkspaceMemberRepository(session)

async def get_workspace_provisioning_service(
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    workspace_settings_repo: WorkspaceSettingsRepository = Depends(get_workspace_settings_repository),
    workspace_member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
) -> WorkspaceProvisioningService:
    return WorkspaceProvisioningService(workspace_repo, workspace_settings_repo, workspace_member_repo)

async def get_workspace_management_service(
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    workspace_member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    session: AsyncSession = Depends(get_async_session),
    request: Request = None,
) -> WorkspaceManagementService:
    from backend.core.dependencies.auth import get_optional_user
    user = None
    if request is not None:
        user = await get_optional_user(request)
        if user is None and hasattr(request, "state"):
            user = getattr(request.state, "user_context", None)

    user_role_str = ""
    if user is not None and hasattr(user, "role"):
        user_role_str = str(user.role).upper()
        if user_role_str.startswith("ROLE."):
            user_role_str = user_role_str.split(".", 1)[1]

    if user_role_str == "PLATFORM_AUDITOR":
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Auditor is not authorized to access workspace configuration or metadata.",
        )

    if user_role_str == "PLATFORM_SUPPORT":
        from fastapi import HTTPException, status
        if request is not None and request.method not in ("GET", "HEAD", "OPTIONS"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform Support is strictly read-only and cannot mutate workspaces.",
            )
        if request is not None:
            from backend.core.permissions.guards import validate_diagnostic_ticket, record_diagnostic_access
            ticket_id = request.headers.get("X-Justification-Ticket-ID")
            ticket = validate_diagnostic_ticket(ticket_id)

            target_ws_id = None
            if hasattr(request, "path_params") and "workspace_id" in request.path_params:
                try:
                    import uuid
                    target_ws_id = uuid.UUID(str(request.path_params["workspace_id"]))
                except (ValueError, TypeError):
                    pass

            if session is not None:
                await record_diagnostic_access(
                    session=session,
                    user_id=user.id,
                    user_role="PLATFORM_SUPPORT",
                    action="DIAGNOSTIC_WORKSPACE_METADATA_READ",
                    resource_type="workspace",
                    resource_id=str(target_ws_id) if target_ws_id else "",
                    ticket_id=ticket,
                    tenant_id=target_ws_id,
                )

            class _DiagnosticWorkspaceMemberRepoProxy:
                def __init__(self, real_repo, diagnostic_user_id):
                    self._real_repo = real_repo
                    self._diagnostic_user_id = str(diagnostic_user_id)

                async def get_membership(self, workspace_id, user_id, *args, **kwargs):
                    real_member = await self._real_repo.get_membership(workspace_id, user_id, *args, **kwargs)
                    if real_member is not None:
                        return real_member
                    if str(user_id) == self._diagnostic_user_id:
                        import uuid
                        from backend.models.entities.workspace_member import WorkspaceMember, MemberStatus
                        return WorkspaceMember(
                            id=uuid.uuid4(),
                            workspace_id=workspace_id,
                            user_id=user_id,
                            role="MEMBER",
                            status=MemberStatus.ACTIVE.value,
                            is_deleted=False,
                        )
                    return None

                def __getattr__(self, name):
                    return getattr(self._real_repo, name)

            return WorkspaceManagementService(workspace_repo, _DiagnosticWorkspaceMemberRepoProxy(workspace_member_repo, user.id))

    return WorkspaceManagementService(workspace_repo, workspace_member_repo)

from backend.services.workspace.membership_service import WorkspaceMembershipService


async def get_workspace_membership_service(
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> WorkspaceMembershipService:
    return WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

from backend.repositories.workspace_invitation import WorkspaceInvitationRepository
from backend.services.email.provider import get_email_provider
from backend.services.workspace.invitation_expiration_worker import (
    WorkspaceInvitationExpirationWorker,
)
from backend.services.workspace.invitation_service import WorkspaceInvitationService


async def get_workspace_invitation_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceInvitationRepository:
    return WorkspaceInvitationRepository(session)

async def get_workspace_invitation_service(
    invitation_repo: WorkspaceInvitationRepository = Depends(get_workspace_invitation_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    settings_repo: WorkspaceSettingsRepository = Depends(get_workspace_settings_repository),
) -> WorkspaceInvitationService:
    email_provider = get_email_provider()
    return WorkspaceInvitationService(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
        workspace_repo=workspace_repo,
        settings_repo=settings_repo,
        email_provider=email_provider,
    )

async def get_workspace_invitation_expiration_worker(
    invitation_service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> WorkspaceInvitationExpirationWorker:
    return WorkspaceInvitationExpirationWorker(invitation_service)


async def get_workspace_settings_service(
    settings_repo: WorkspaceSettingsRepository = Depends(get_workspace_settings_repository),
    history_repo: WorkspaceSettingsHistoryRepository = Depends(get_workspace_settings_history_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
) -> WorkspaceSettingsService:
    return WorkspaceSettingsService(settings_repo, history_repo, workspace_repo, member_repo)


from backend.services.workspace.join_code_service import JoinCodeService


async def get_join_code_service(
    settings_repo: WorkspaceSettingsRepository = Depends(get_workspace_settings_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> JoinCodeService:
    return JoinCodeService(settings_repo=settings_repo, member_repo=member_repo, workspace_repo=workspace_repo)


from backend.services.workspace.workspace_joining_service import WorkspaceJoiningService


async def get_workspace_joining_service(
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    settings_repo: WorkspaceSettingsRepository = Depends(get_workspace_settings_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    join_code_service: JoinCodeService = Depends(get_join_code_service),
    invitation_service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> WorkspaceJoiningService:
    return WorkspaceJoiningService(
        workspace_repo=workspace_repo,
        settings_repo=settings_repo,
        member_repo=member_repo,
        join_code_service=join_code_service,
        invitation_service=invitation_service,
    )


from backend.core.security.jwt import JWTService, get_jwt_service
from backend.services.workspace.workspace_switching_service import WorkspaceSwitchingService


async def get_workspace_switching_service(
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
) -> WorkspaceSwitchingService:
    return WorkspaceSwitchingService(
        workspace_repo=workspace_repo,
        member_repo=member_repo,
        jwt_service=get_jwt_service(),
    )





# Feature Flag Dependencies

from backend.repositories.feature_flag import (
    FeatureFlagHistoryRepository,
    FeatureFlagRepository,
    FeatureFlagWorkspaceRuleRepository,
)
from backend.services.feature_flag.evaluation_service import FeatureFlagEvaluationService
from backend.services.feature_flag.management_service import FeatureFlagManagementService


async def get_feature_flag_repository(session: AsyncSession = Depends(get_db)) -> FeatureFlagRepository:
    return FeatureFlagRepository(session)

async def get_feature_flag_workspace_rule_repository(session: AsyncSession = Depends(get_db)) -> FeatureFlagWorkspaceRuleRepository:
    return FeatureFlagWorkspaceRuleRepository(session)

async def get_feature_flag_history_repository(session: AsyncSession = Depends(get_db)) -> FeatureFlagHistoryRepository:
    return FeatureFlagHistoryRepository(session)

async def get_feature_flag_evaluation_service(
    flag_repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
    rule_repo: FeatureFlagWorkspaceRuleRepository = Depends(get_feature_flag_workspace_rule_repository),
) -> FeatureFlagEvaluationService:
    return FeatureFlagEvaluationService(flag_repo, rule_repo)

async def get_feature_flag_management_service(
    flag_repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
    rule_repo: FeatureFlagWorkspaceRuleRepository = Depends(get_feature_flag_workspace_rule_repository),
    history_repo: FeatureFlagHistoryRepository = Depends(get_feature_flag_history_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
) -> FeatureFlagManagementService:
    return FeatureFlagManagementService(flag_repo, rule_repo, history_repo, workspace_repo, member_repo)


from backend.repositories.workspace_access_request import WorkspaceAccessRequestRepository
from backend.services.workspace.access_request_service import AccessRequestService


async def get_workspace_access_request_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceAccessRequestRepository:
    return WorkspaceAccessRequestRepository(session)


async def get_access_request_service(
    access_repo: WorkspaceAccessRequestRepository = Depends(get_workspace_access_request_repository),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
) -> AccessRequestService:
    return AccessRequestService(access_repo, member_repo, workspace_repo)


