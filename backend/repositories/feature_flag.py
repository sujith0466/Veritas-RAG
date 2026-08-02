"""Feature Flag repositories for ORM persistence and querying."""

from collections.abc import Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.feature_flag import FeatureFlag
from backend.models.entities.feature_flag_history import FeatureFlagHistory
from backend.models.entities.feature_flag_workspace_rule import FeatureFlagWorkspaceRule
from backend.repositories.base import BaseRepository


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    """Repository for master feature flag configurations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FeatureFlag)

    async def get_by_key(self, key: str) -> FeatureFlag | None:
        """Fetch feature flag by its unique key."""
        stmt = select(FeatureFlag).where(
            FeatureFlag.key == key,
            FeatureFlag.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key_for_update(self, key: str) -> FeatureFlag | None:
        """Fetch feature flag by its key with row-level lock."""
        stmt = (
            select(FeatureFlag)
            .where(
                FeatureFlag.key == key,
                FeatureFlag.is_deleted.is_(False),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_flags(self) -> Sequence[FeatureFlag]:
        """List all non-deleted feature flags."""
        stmt = select(FeatureFlag).where(FeatureFlag.is_deleted.is_(False))
        result = await self.session.execute(stmt)
        return result.scalars().all()


class FeatureFlagWorkspaceRuleRepository(BaseRepository[FeatureFlagWorkspaceRule]):
    """Repository for workspace override rules."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FeatureFlagWorkspaceRule)

    async def get_by_flag_and_workspace(
        self, flag_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> FeatureFlagWorkspaceRule | None:
        """Fetch workspace override rule for a flag."""
        stmt = select(FeatureFlagWorkspaceRule).where(
            FeatureFlagWorkspaceRule.flag_id == flag_id,
            FeatureFlagWorkspaceRule.workspace_id == workspace_id,
            FeatureFlagWorkspaceRule.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_flag_and_workspace_for_update(
        self, flag_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> FeatureFlagWorkspaceRule | None:
        """Fetch workspace override rule with row lock."""
        stmt = (
            select(FeatureFlagWorkspaceRule)
            .where(
                FeatureFlagWorkspaceRule.flag_id == flag_id,
                FeatureFlagWorkspaceRule.workspace_id == workspace_id,
                FeatureFlagWorkspaceRule.is_deleted.is_(False),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_rules_for_workspace(
        self, workspace_id: uuid.UUID
    ) -> Sequence[FeatureFlagWorkspaceRule]:
        """List all override rules configured for a workspace."""
        stmt = select(FeatureFlagWorkspaceRule).where(
            FeatureFlagWorkspaceRule.workspace_id == workspace_id,
            FeatureFlagWorkspaceRule.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class FeatureFlagHistoryRepository(BaseRepository[FeatureFlagHistory]):
    """Repository for feature flag audit and rollback snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FeatureFlagHistory)

    async def list_history_for_flag(
        self,
        flag_id: uuid.UUID,
        workspace_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> Sequence[FeatureFlagHistory]:
        """List version history snapshots for a flag and optional workspace."""
        stmt = select(FeatureFlagHistory).where(
            FeatureFlagHistory.flag_id == flag_id,
            FeatureFlagHistory.is_deleted.is_(False),
        )
        if workspace_id is not None:
            stmt = stmt.where(FeatureFlagHistory.workspace_id == workspace_id)
        stmt = stmt.order_by(FeatureFlagHistory.version.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
