"""Folder Repository."""

from collections.abc import Sequence
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.folder import Folder
from backend.repositories.base import BaseRepository


class FolderRepository(BaseRepository[Folder]):
    """Repository for managing folders with tenant isolation."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Folder)

    async def count_folders(self, workspace_id: uuid.UUID) -> int:
        """Count active folders in a workspace."""
        stmt = select(func.count()).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id_in_workspace(self, folder_id: uuid.UUID, workspace_id: uuid.UUID) -> Folder | None:
        """Fetch a single active folder belonging to the workspace."""
        stmt = select(self.model_class).where(
            self.model_class.id == folder_id,
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_root_folders(self, workspace_id: uuid.UUID, skip: int = 0, limit: int = 20) -> Sequence[Folder]:
        """Fetch active root folders for a workspace."""
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.parent_id.is_(None),
            self.model_class.is_deleted.is_(False),
        ).order_by(self.model_class.name).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_children(self, parent_id: uuid.UUID, workspace_id: uuid.UUID, skip: int = 0, limit: int = 20) -> Sequence[Folder]:
        """Fetch active children folders for a given parent in a workspace."""
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.parent_id == parent_id,
            self.model_class.is_deleted.is_(False),
        ).order_by(self.model_class.name).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def exists_name_in_parent(self, workspace_id: uuid.UUID, parent_id: uuid.UUID | None, normalized_name: str, exclude_id: uuid.UUID | None = None) -> bool:
        """Check if a folder with the given lowercased name already exists under the parent."""
        conditions = [
            self.model_class.workspace_id == workspace_id,
            func.lower(self.model_class.name) == normalized_name,
            self.model_class.is_deleted.is_(False),
        ]

        if parent_id is None:
            conditions.append(self.model_class.parent_id.is_(None))
        else:
            conditions.append(self.model_class.parent_id == parent_id)

        if exclude_id is not None:
            conditions.append(self.model_class.id != exclude_id)

        stmt = select(func.count()).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    async def get_subtree_ids(self, folder_id: uuid.UUID, workspace_id: uuid.UUID) -> Sequence[uuid.UUID]:
        """Get all IDs in the subtree using a recursive CTE bounded to workspace."""
        from sqlalchemy.orm import aliased

        folders = self.model_class

        # Anchor
        anchor = select(folders.id).where(
            folders.id == folder_id,
            folders.workspace_id == workspace_id
        ).cte("subtree", recursive=True)

        # Recursive term
        f_alias = aliased(folders)
        recursive = select(f_alias.id).join(
            anchor, f_alias.parent_id == anchor.c.id
        ).where(
            f_alias.workspace_id == workspace_id,
            f_alias.is_deleted.is_(False)
        )

        subtree = anchor.union_all(recursive)

        stmt = select(subtree.c.id).limit(50000)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_ancestors(self, folder_id: uuid.UUID, workspace_id: uuid.UUID) -> Sequence[Folder]:
        """Fetch all ancestors of a folder based on its path."""
        folder = await self.get_by_id_in_workspace(folder_id, workspace_id)
        if not folder or not folder.path:
            return []

        path_ids_str = folder.path.split("/")
        # The path includes the workspace_id at the start potentially, let's just parse UUIDs
        # According to design, path = "ws_id/root_id/.../folder_id"
        ancestor_ids = []
        for part in path_ids_str:
            try:
                ancestor_ids.append(uuid.UUID(part))
            except ValueError:
                pass

        # Fetch those that are folders
        stmt = select(self.model_class).where(
            self.model_class.id.in_(ancestor_ids),
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted.is_(False)
        ).order_by(self.model_class.depth)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_folders(self, workspace_id: uuid.UUID, query: str, skip: int = 0, limit: int = 50, parent_id: uuid.UUID | None = None) -> Sequence[Folder]:
        """Search folders by name prefix."""
        conditions = [
            self.model_class.workspace_id == workspace_id,
            self.model_class.name.ilike(f"{query}%"),
            self.model_class.is_deleted.is_(False)
        ]
        if parent_id is not None:
            conditions.append(self.model_class.parent_id == parent_id)

        stmt = select(self.model_class).where(and_(*conditions)).order_by(self.model_class.name).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_folder_with_lock(self, folder_id: uuid.UUID, workspace_id: uuid.UUID) -> Folder | None:
        """Fetch a single folder with FOR UPDATE lock."""
        stmt = select(self.model_class).where(
            self.model_class.id == folder_id,
            self.model_class.workspace_id == workspace_id,
        ).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def check_cycle(self, target_path: str, source_path: str) -> bool:
        """Check if target is a descendant of source to prevent cycles.
        Because paths are UUIDs joined by dots or slashes, we can check prefix.
        Target path: 'ws/root/.../target'
        Source path: 'ws/root/.../source'
        If target_path starts with source_path, it's a cycle.
        """
        # Add separator to avoid partial UUID match, though UUIDs are fixed length
        prefix = f"{source_path}/"
        return target_path == source_path or target_path.startswith(prefix)

    async def get_subtree_height(self, folder_id: uuid.UUID, workspace_id: uuid.UUID) -> int:
        """Calculate max depth in subtree relative to root."""
        from sqlalchemy.orm import aliased
        folders = self.model_class

        anchor = select(folders.id, folders.depth).where(
            folders.id == folder_id,
            folders.workspace_id == workspace_id
        ).cte("subtree", recursive=True)

        f_alias = aliased(folders)
        recursive = select(f_alias.id, f_alias.depth).join(
            anchor, f_alias.parent_id == anchor.c.id
        ).where(
            f_alias.workspace_id == workspace_id
        )

        subtree = anchor.union_all(recursive)

        # Max depth - base depth gives height
        base_stmt = select(folders.depth).where(folders.id == folder_id)
        base_depth = (await self.session.execute(base_stmt)).scalar_one_or_none() or 0

        stmt = select(func.max(subtree.c.depth))
        result = await self.session.execute(stmt)
        max_depth = result.scalar_one_or_none() or base_depth

        return max_depth - base_depth

    async def get_eligible_for_purge(self, limit: int = 50) -> Sequence[Folder]:
        """Fetch root-level soft-deleted folders eligible for hard deletion."""
        # Find folders where purge_at <= NOW() and purge_status IS NULL
        # and parent_id is either NULL or the parent is NOT soft_deleted.

        # We can implement the parent check using a subquery
        from sqlalchemy import exists
        parent_alias = self.model_class.__table__.alias("parent_folder")

        parent_is_soft_deleted = select(1).where(
            parent_alias.c.id == self.model_class.parent_id,
            parent_alias.c.is_deleted == True
        )

        stmt = select(self.model_class).where(
            self.model_class.is_deleted == True,
            self.model_class.purge_at <= func.now(),
            self.model_class.purge_status.is_(None),
            # Root folder OR parent is not soft-deleted
            (self.model_class.parent_id.is_(None) | ~exists(parent_is_soft_deleted))
        ).order_by(self.model_class.purge_at.asc()).limit(limit).with_for_update(skip_locked=True)

        result = await self.session.execute(stmt)
        return result.scalars().all()
