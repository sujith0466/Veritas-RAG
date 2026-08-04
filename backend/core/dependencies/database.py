"""FastAPI database and repository dependency providers.

Yields request-scoped database sessions, Redis/Qdrant clients, and repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Depends

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
) -> WorkspaceManagementService:
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


