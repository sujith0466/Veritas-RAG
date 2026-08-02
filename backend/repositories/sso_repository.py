"""Repository for SSO Config Management."""

from collections.abc import Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.identity_provider import IdentityProvider
from backend.repositories.base import BaseRepository


class IdentityProviderRepository(BaseRepository[IdentityProvider]):
    """Data access layer for IdentityProvider entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IdentityProvider)

    async def get_by_workspace(self, workspace_id: uuid.UUID) -> Sequence[IdentityProvider]:
        """Fetch all Identity Providers for a workspace."""
        stmt = select(IdentityProvider).where(
            IdentityProvider.workspace_id == workspace_id,
            IdentityProvider.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_active_for_workspace(self, workspace_id: uuid.UUID) -> IdentityProvider | None:
        """Fetch the active Identity Provider for a workspace."""
        stmt = select(IdentityProvider).where(
            IdentityProvider.workspace_id == workspace_id,
            IdentityProvider.is_active.is_(True),
            IdentityProvider.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
