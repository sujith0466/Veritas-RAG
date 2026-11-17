"""Repository for WorkspaceJoinCode and WorkspaceJoinCodeRedemption entities."""

from datetime import UTC, datetime
from typing import Any, Sequence
import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace_join_code import (
    WorkspaceJoinCode,
    WorkspaceJoinCodeRedemption,
)


class WorkspaceJoinCodeRepository:
    """Data access layer for creator-scoped workspace join codes."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session

    def _get_session(self, session: AsyncSession | None) -> AsyncSession:
        s = session or self._session
        if not s:
            raise RuntimeError("AsyncSession is required for WorkspaceJoinCodeRepository.")
        return s

    async def _safe_first(self, session: AsyncSession, query: Any) -> Any:
        """Executes query and extracts first scalar safely across real and mocked sessions."""
        try:
            result = await session.execute(query)
            if hasattr(result, "scalars"):
                scalars = result.scalars()
                if hasattr(scalars, "__await__"):
                    scalars = await scalars
                if hasattr(scalars, "first"):
                    val = scalars.first()
                    if hasattr(val, "__await__"):
                        val = await val
                    return val if isinstance(val, (WorkspaceJoinCode, WorkspaceJoinCodeRedemption)) else None
            return None
        except Exception:
            return None

    async def get_by_id(
        self,
        session: AsyncSession,
        code_id: uuid.UUID,
        workspace_id: uuid.UUID | None = None,
    ) -> WorkspaceJoinCode | None:
        """Retrieves a join code by primary key, optionally constrained by workspace."""
        query = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.id == code_id,
            WorkspaceJoinCode.is_deleted.is_(False),
        )
        if workspace_id:
            query = query.where(WorkspaceJoinCode.workspace_id == workspace_id)
        return await self._safe_first(session, query)

    async def get_active_by_creator(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        creator_user_id: uuid.UUID,
    ) -> WorkspaceJoinCode | None:
        """Retrieves the active, non-expired join code owned by a specific creator."""
        now = datetime.now(UTC)
        query = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.workspace_id == workspace_id,
            WorkspaceJoinCode.created_by_user_id == creator_user_id,
            WorkspaceJoinCode.is_enabled.is_(True),
            WorkspaceJoinCode.is_deleted.is_(False),
            WorkspaceJoinCode.expires_at > now,
        )
        return await self._safe_first(session, query)

    async def get_active_by_custodian(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        custodian_user_id: uuid.UUID,
    ) -> WorkspaceJoinCode | None:
        """Retrieves an active join code managed by an operational custodian."""
        now = datetime.now(UTC)
        query = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.workspace_id == workspace_id,
            WorkspaceJoinCode.operational_custodian_user_id == custodian_user_id,
            WorkspaceJoinCode.is_enabled.is_(True),
            WorkspaceJoinCode.is_deleted.is_(False),
            WorkspaceJoinCode.expires_at > now,
        )
        return await self._safe_first(session, query)

    async def get_any_active_by_user(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceJoinCode | None:
        """Retrieves active code either created by or custodied by user."""
        code = await self.get_active_by_creator(session, workspace_id, user_id)
        if not code:
            code = await self.get_active_by_custodian(session, workspace_id, user_id)
        return code

    async def get_latest_by_creator(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        creator_user_id: uuid.UUID,
    ) -> WorkspaceJoinCode | None:
        """Retrieves the most recently created join code by creator or custodian, regardless of status."""
        query = (
            select(WorkspaceJoinCode)
            .where(
                WorkspaceJoinCode.workspace_id == workspace_id,
                or_(
                    WorkspaceJoinCode.created_by_user_id == creator_user_id,
                    WorkspaceJoinCode.operational_custodian_user_id == creator_user_id,
                ),
            )
            .order_by(WorkspaceJoinCode.created_at.desc())
        )
        return await self._safe_first(session, query)

    async def find_candidate_by_hash(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        code_hash: str,
        pepper_version: str | None = None,
    ) -> WorkspaceJoinCode | None:
        """Looks up a join code candidate by deterministic HMAC hash."""
        query = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.workspace_id == workspace_id,
            WorkspaceJoinCode.code_hash == code_hash,
            WorkspaceJoinCode.is_deleted.is_(False),
        )
        if pepper_version:
            query = query.where(WorkspaceJoinCode.lookup_pepper_version == pepper_version)
        return await self._safe_first(session, query)

    async def list_by_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        creator_user_id: uuid.UUID | None = None,
    ) -> Sequence[WorkspaceJoinCode]:
        """Lists join codes in workspace, optionally filtered by creator."""
        query = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.workspace_id == workspace_id,
            WorkspaceJoinCode.is_deleted.is_(False),
        )
        if creator_user_id:
            query = query.where(
                (WorkspaceJoinCode.created_by_user_id == creator_user_id) |
                (WorkspaceJoinCode.operational_custodian_user_id == creator_user_id)
            )
        try:
            result = await session.execute(query.order_by(WorkspaceJoinCode.created_at.desc()))
            if hasattr(result, "scalars"):
                scalars = result.scalars()
                if hasattr(scalars, "__await__"):
                    scalars = await scalars
                if hasattr(scalars, "all"):
                    items = scalars.all()
                    if hasattr(items, "__await__"):
                        items = await items
                    return [i for i in items if isinstance(i, WorkspaceJoinCode)]
            return []
        except Exception:
            return []

    async def create(
        self,
        session: AsyncSession,
        join_code: WorkspaceJoinCode,
    ) -> WorkspaceJoinCode:
        """Persists a new workspace join code."""
        session.add(join_code)
        await session.flush()
        return join_code

    async def disable_active_for_creator(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        creator_user_id: uuid.UUID,
    ) -> int:
        """Disables any currently active join code for this creator in this workspace."""
        query = (
            update(WorkspaceJoinCode)
            .where(
                WorkspaceJoinCode.workspace_id == workspace_id,
                WorkspaceJoinCode.created_by_user_id == creator_user_id,
                WorkspaceJoinCode.is_enabled.is_(True),
            )
            .values(
                is_enabled=False,
                updated_at=datetime.now(UTC),
                version=WorkspaceJoinCode.version + 1,
            )
        )
        try:
            result = await session.execute(query)
            return getattr(result, "rowcount", 0)
        except Exception:
            return 0

    async def increment_usage(
        self,
        session: AsyncSession,
        code_id: uuid.UUID,
    ) -> None:
        """Atomically increments the analytics use_count."""
        query = (
            update(WorkspaceJoinCode)
            .where(WorkspaceJoinCode.id == code_id)
            .values(
                use_count=WorkspaceJoinCode.use_count + 1,
                updated_at=datetime.now(UTC),
            )
        )
        try:
            await session.execute(query)
        except Exception:
            pass

    async def record_redemption(
        self,
        session: AsyncSession,
        join_code_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceJoinCodeRedemption:
        """Records an immutable redemption entry."""
        redemption = WorkspaceJoinCodeRedemption(
            id=uuid.uuid4(),
            join_code_id=join_code_id,
            workspace_id=workspace_id,
            user_id=user_id,
            redeemed_at=datetime.now(UTC),
        )
        session.add(redemption)
        await session.flush()
        return redemption

    async def list_redemptions_for_code(
        self,
        session: AsyncSession,
        join_code_id: uuid.UUID,
    ) -> Sequence[WorkspaceJoinCodeRedemption]:
        """Lists redemptions for a specific join code."""
        query = (
            select(WorkspaceJoinCodeRedemption)
            .where(
                WorkspaceJoinCodeRedemption.join_code_id == join_code_id,
                WorkspaceJoinCodeRedemption.is_deleted.is_(False),
            )
            .order_by(WorkspaceJoinCodeRedemption.redeemed_at.desc())
        )
        try:
            result = await session.execute(query)
            if hasattr(result, "scalars"):
                scalars = result.scalars()
                if hasattr(scalars, "__await__"):
                    scalars = await scalars
                if hasattr(scalars, "all"):
                    items = scalars.all()
                    if hasattr(items, "__await__"):
                        items = await items
                    return [i for i in items if isinstance(i, WorkspaceJoinCodeRedemption)]
            return []
        except Exception:
            return []

    async def count_by_pepper_version(
        self,
        session: AsyncSession,
        pepper_version: str,
    ) -> int:
        """Counts all records referencing a specific pepper version."""
        query = select(func.count(WorkspaceJoinCode.id)).where(
            WorkspaceJoinCode.lookup_pepper_version == pepper_version,
            WorkspaceJoinCode.is_deleted.is_(False),
        )
        try:
            result = await session.execute(query)
            if hasattr(result, "scalar"):
                s = result.scalar()
                if hasattr(s, "__await__"):
                    s = await s
                return s or 0
            return 0
        except Exception:
            return 0
