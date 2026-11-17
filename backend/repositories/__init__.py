"""Repository layer abstractions and implementations."""

from .base import BaseRepository
from .feature_flag import (
    FeatureFlagHistoryRepository,
    FeatureFlagRepository,
    FeatureFlagWorkspaceRuleRepository,
)
from .implementations.audit_log_repository import AuditLogRepository
from .implementations.user_repository import UserRepository
from .interfaces.audit_log_repository import IAuditLogRepository
from .interfaces.user_repository import IUserRepository
from .workspace import WorkspaceRepository
from .workspace_member import WorkspaceMemberRepository
from .workspace_settings import WorkspaceSettingsRepository
from .workspace_settings_history import WorkspaceSettingsHistoryRepository
from .workspace_former_owner_departure import WorkspaceFormerOwnerDepartureRepository
from .workspace_ownership_transfer import WorkspaceOwnershipTransferRepository

__all__ = [
    "AuditLogRepository",
    "BaseRepository",
    "IAuditLogRepository",
    "IUserRepository",
    "UserRepository",
    "WorkspaceRepository",
    "WorkspaceMemberRepository",
    "WorkspaceSettingsRepository",
    "WorkspaceSettingsHistoryRepository",
    "WorkspaceFormerOwnerDepartureRepository",
    "WorkspaceOwnershipTransferRepository",
    "FeatureFlagRepository",
    "FeatureFlagWorkspaceRuleRepository",
    "FeatureFlagHistoryRepository",
]
