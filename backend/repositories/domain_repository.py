"""Repository for Domain Management."""

from collections.abc import Sequence
from datetime import UTC, datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace_domain import DomainCooldown, WorkspaceDomain
from backend.repositories.base import BaseRepository


class WorkspaceDomainRepository(BaseRepository[WorkspaceDomain]):
    """Data access layer for WorkspaceDomain entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkspaceDomain)

    async def get_by_domain_name(self, domain_name: str) -> WorkspaceDomain | None:
        """Fetch a domain by its name, ignoring deleted."""
        stmt = select(WorkspaceDomain).where(
            WorkspaceDomain.domain_name == domain_name,
            WorkspaceDomain.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_workspace(self, workspace_id: uuid.UUID) -> Sequence[WorkspaceDomain]:
        """Fetch all domains for a given workspace."""
        stmt = select(WorkspaceDomain).where(
            WorkspaceDomain.workspace_id == workspace_id,
            WorkspaceDomain.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_primary_for_workspace(self, workspace_id: uuid.UUID) -> WorkspaceDomain | None:
        """Fetch the primary domain for a workspace."""
        stmt = select(WorkspaceDomain).where(
            WorkspaceDomain.workspace_id == workspace_id,
            WorkspaceDomain.is_primary.is_(True),
            WorkspaceDomain.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def is_verified_globally(self, domain_name: str) -> bool:
        """Check if a domain is verified by ANY workspace."""
        stmt = select(WorkspaceDomain).where(
            WorkspaceDomain.domain_name == domain_name,
            WorkspaceDomain.status == "VERIFIED",
            WorkspaceDomain.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_cooldown(self, domain_name: str) -> DomainCooldown | None:
        """Check if a domain is currently in cooldown."""
        now = datetime.now(UTC)
        stmt = select(DomainCooldown).where(
            DomainCooldown.domain_name == domain_name,
            DomainCooldown.cooldown_expires_at > now
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_cooldown(self, cooldown: DomainCooldown) -> None:
        """Add a domain to the cooldown table."""
        self.session.add(cooldown)
        await self.session.flush()
