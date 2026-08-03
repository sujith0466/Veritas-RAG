"""Folder Domain Service."""

import re
import unicodedata
import uuid
from datetime import datetime, UTC

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from backend.core.events.dispatcher import EventDispatcher
from backend.repositories.folder_repository import FolderRepository
from backend.models.entities.folder import Folder
from backend.models.entities.audit_log import AuditLog
from backend.services.folder.events import (
    FolderCreatedEvent, FolderRenamedEvent, FolderSoftDeletedEvent, FolderRestoredEvent
)
from backend.cache.manager import CacheManager
from backend.cache.keys import CacheKeyBuilder, TTLProfile
from backend.cache.client import get_redis_client


class FolderError(Exception):
    """Base exception for Folder domain errors."""


class FolderNotFoundError(FolderError):
    """Folder not found."""


class FolderConflictError(FolderError):
    """Conflict such as name collision or version mismatch."""
    def __init__(self, message: str, current_version: int | None = None, current_name: str | None = None):
        super().__init__(message)
        self.current_version = current_version
        self.current_name = current_name


class FolderRateLimitError(FolderError):
    """Rate limit exceeded."""


class FolderParentDeletedError(FolderError):
    """Parent is deleted."""


def slugify(text: str) -> str:
    """Generate a URL-safe slug from text."""
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)


class FolderCache:
    """Helper for folder cache keys and pipelines."""
    
    @staticmethod
    def get_cache_key(workspace_id: uuid.UUID, folder_id: uuid.UUID) -> str:
        return CacheKeyBuilder.build(str(workspace_id), "folder", "entity", str(folder_id))
        
    @staticmethod
    def get_children_prefix(workspace_id: uuid.UUID, parent_id: uuid.UUID | None) -> str:
        p_id = str(parent_id) if parent_id else "root"
        # The key isn't standard, we must invalidate all pages. We can scan for them.
        # Actually CacheKeyBuilder doesn't easily support wildcards, we'll build manually.
        tenant_str = str(workspace_id).replace(":", "_")
        return f"{CacheKeyBuilder.VERSION_PREFIX}:{tenant_str}:folder:children:{p_id}:*"
        
    @staticmethod
    def get_breadcrumb_key(workspace_id: uuid.UUID, folder_id: uuid.UUID) -> str:
        return CacheKeyBuilder.build(str(workspace_id), "folder", "breadcrumbs", str(folder_id))
        
    @staticmethod
    async def invalidate_for_rename(workspace_id: uuid.UUID, folder_id: uuid.UUID, parent_id: uuid.UUID | None, descendant_ids: list[uuid.UUID]):
        client = get_redis_client()
        keys_to_delete = [
            FolderCache.get_cache_key(workspace_id, folder_id),
            FolderCache.get_breadcrumb_key(workspace_id, folder_id)
        ]
        for d_id in descendant_ids:
            keys_to_delete.append(FolderCache.get_breadcrumb_key(workspace_id, d_id))
            
        # Scan and add children keys
        cursor = 0
        pattern = FolderCache.get_children_prefix(workspace_id, parent_id)
        while True:
            cursor, keys = await client.scan(cursor, match=pattern, count=100)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break
                
        if keys_to_delete:
            await client.delete(*keys_to_delete)

    @staticmethod
    async def invalidate_for_delete_restore(workspace_id: uuid.UUID, folder_id: uuid.UUID, parent_id: uuid.UUID | None):
        client = get_redis_client()
        keys_to_delete = [
            FolderCache.get_cache_key(workspace_id, folder_id)
        ]
        cursor = 0
        pattern = FolderCache.get_children_prefix(workspace_id, parent_id)
        while True:
            cursor, keys = await client.scan(cursor, match=pattern, count=100)
            keys_to_delete.extend(keys)
            if cursor == 0:
                break
        if keys_to_delete:
            await client.delete(*keys_to_delete)


class FolderService:
    """Service for Folder creation, rename, soft delete, and restore."""

    MAX_DEPTH = 10
    MAX_FOLDERS_PER_WORKSPACE = 100000

    def __init__(self, session: AsyncSession, dispatcher: EventDispatcher):
        self.session = session
        self.dispatcher = dispatcher
        self.repo = FolderRepository(session)

    async def _check_rate_limits(self, workspace_id: uuid.UUID, actor_id: uuid.UUID):
        client = get_redis_client()
        user_key = f"rate:ws:{workspace_id}:user:{actor_id}:folder_create"
        ws_key = f"rate:ws:{workspace_id}:folder_create"
        
        # We can implement a simple sliding window or fixed window counter using Redis
        async with client.pipeline() as pipe:
            pipe.incr(user_key)
            pipe.expire(user_key, 60, nx=True)
            pipe.incr(ws_key)
            pipe.expire(ws_key, 60, nx=True)
            user_count, _, ws_count, _ = await pipe.execute()
            
        if user_count > 60:
            raise FolderRateLimitError("User rate limit exceeded for folder creation (60/min).")
        if ws_count > 500:
            raise FolderRateLimitError("Workspace rate limit exceeded for folder creation (500/min).")

    async def create_folder(self, workspace_id: uuid.UUID, actor_id: uuid.UUID, name: str, parent_id: uuid.UUID | None = None) -> Folder:
        """Create a new folder."""
        await self._check_rate_limits(workspace_id, actor_id)
        
        count = await self.repo.count_folders(workspace_id)
        if count >= self.MAX_FOLDERS_PER_WORKSPACE:
            raise FolderRateLimitError(f"Workspace folder limit reached ({self.MAX_FOLDERS_PER_WORKSPACE}).")

        norm_name = name.strip().lower()
        if await self.repo.exists_name_in_parent(workspace_id, parent_id, norm_name):
            raise FolderConflictError(f"A folder named '{name}' already exists in this location.")

        depth = 0
        path = ""
        new_id = uuid.uuid4()

        if parent_id:
            parent = await self.repo.get_by_id_in_workspace(parent_id, workspace_id)
            if not parent:
                raise FolderNotFoundError("Parent folder not found.")
            if parent.depth >= self.MAX_DEPTH - 1:
                raise FolderConflictError(f"Maximum folder depth of {self.MAX_DEPTH} exceeded.")
            depth = parent.depth + 1
            path = f"{parent.path}/{new_id}" if parent.path else f"{parent.id}/{new_id}"
        else:
            path = str(new_id)

        slug = slugify(name)
        # Collision handling for slug is normally handled by appending a number, 
        # but the unique index covers us if there's a race. For simplicity, since exists_name 
        # guards against the same name, we can just insert and catch IntegrityError.

        folder = Folder(
            id=new_id,
            workspace_id=workspace_id,
            parent_id=parent_id,
            name=name.strip(),
            slug=slug,
            depth=depth,
            path=path,
            created_by_user_id=actor_id
        )
        self.session.add(folder)
        
        audit_log = AuditLog(
            action="folder.created",
            user_id=actor_id,
            resource_type="folder",
            resource_id=str(new_id),
            details={"name": folder.name, "parent_id": str(parent_id) if parent_id else None}
        )
        self.session.add(audit_log)
        
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise FolderConflictError("Folder name or slug already exists.")

        event = FolderCreatedEvent(workspace_id=workspace_id, folder_id=new_id, actor_id=actor_id)
        await self.dispatcher.publish(event)
        
        await FolderCache.invalidate_for_delete_restore(workspace_id, new_id, parent_id)
        return folder

    async def rename_folder(self, workspace_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID, new_name: str, expected_version: int) -> Folder:
        """Rename a folder."""
        folder = await self.repo.get_by_id_in_workspace(folder_id, workspace_id)
        if not folder:
            raise FolderNotFoundError("Folder not found.")
            
        if expected_version != folder.version:
            raise FolderConflictError("Folder was updated elsewhere.", current_version=folder.version, current_name=folder.name)

        norm_name = new_name.strip().lower()
        if folder.name.strip().lower() == norm_name:
            # No-op
            return folder
            
        if await self.repo.exists_name_in_parent(workspace_id, folder.parent_id, norm_name, exclude_id=folder_id):
            raise FolderConflictError(f"A folder named '{new_name}' already exists in this location.")

        old_name = folder.name
        folder.name = new_name.strip()
        folder.slug = slugify(new_name)
        folder.version += 1
        
        audit_log = AuditLog(
            action="folder.renamed",
            user_id=actor_id,
            resource_type="folder",
            resource_id=str(folder_id),
            details={"old_name": old_name, "new_name": folder.name}
        )
        self.session.add(audit_log)
        await self.session.flush()

        event = FolderRenamedEvent(
            workspace_id=workspace_id, folder_id=folder_id, old_name=old_name, new_name=folder.name, actor_id=actor_id
        )
        await self.dispatcher.publish(event)
        
        descendant_ids = await self.repo.get_subtree_ids(folder_id, workspace_id)
        await FolderCache.invalidate_for_rename(workspace_id, folder_id, folder.parent_id, [d for d in descendant_ids if d != folder_id])
        return folder

    async def soft_delete_folder(self, workspace_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID, expected_version: int) -> str:
        """Soft delete a folder and enqueue cascade worker."""
        folder = await self.repo.get_by_id_in_workspace(folder_id, workspace_id)
        if not folder:
            raise FolderNotFoundError("Folder not found.")
            
        if expected_version != folder.version:
            raise FolderConflictError("Folder was updated elsewhere.", current_version=folder.version, current_name=folder.name)
            
        # Prevent concurrent cascade triggers using Redis lock
        client = get_redis_client()
        lock_key = f"lock:ws:{workspace_id}:folder:{folder_id}:cascade"
        acquired = await client.set(lock_key, "1", nx=True, px=300000)
        if not acquired:
            # Already in progress
            return "duplicate"

        from datetime import timedelta
        folder.is_deleted = True
        folder.deleted_at = datetime.now(UTC)
        folder.deleted_by_user_id = actor_id
        folder.version += 1
        folder.purge_at = folder.deleted_at + timedelta(days=30)
        folder.purge_status = 'scheduled'

        details = {"cascade_pending": True, "parent_id": str(folder.parent_id) if folder.parent_id else None}
        if folder.parent_id is None:
            # Check if this is the last root folder (as a warning)
            root_folders = await self.repo.get_root_folders(workspace_id, limit=2)
            if len([rf for rf in root_folders if rf.id != folder_id]) == 0:
                details["last_root_folder_deleted"] = True

        audit_log = AuditLog(
            action="folder.soft_deleted",
            user_id=actor_id,
            resource_type="folder",
            resource_id=str(folder_id),
            details=details
        )
        self.session.add(audit_log)
        await self.session.flush()
        
        # Enqueue Celery Task
        from backend.tasks.folders import cascade_soft_delete_subtree
        task = cascade_soft_delete_subtree.delay(
            folder_id=str(folder_id),
            workspace_id=str(workspace_id),
            deleted_by_user_id=str(actor_id),
            deleted_at=folder.deleted_at.isoformat()
        )
        audit_log.details["worker_task_id"] = task.id
        
        event = FolderSoftDeletedEvent(workspace_id=workspace_id, folder_id=folder_id, actor_id=actor_id, cascade_pending=True)
        await self.dispatcher.publish(event)
        
        await FolderCache.invalidate_for_delete_restore(workspace_id, folder_id, folder.parent_id)
        return task.id

    async def restore_folder(self, workspace_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID) -> str:
        """Restore a soft-deleted folder and enqueue cascade worker."""
        # Note: Repositories usually filter out is_deleted=True. We bypass or add a method.
        # Let's write raw select to get deleted folder
        from sqlalchemy import select
        stmt = select(Folder).where(
            Folder.id == folder_id,
            Folder.workspace_id == workspace_id,
            Folder.is_deleted.is_(True)
        )
        result = await self.session.execute(stmt)
        folder = result.scalar_one_or_none()
        
        if not folder:
            # It might be active already
            active_folder = await self.repo.get_by_id_in_workspace(folder_id, workspace_id)
            if active_folder:
                raise FolderNotFoundError("This folder is not in a deleted state.")
            raise FolderNotFoundError("Folder not found.")

        if folder.purge_status in ('purging', 'purged'):
            # Return 410 Gone equivalent logic or a specific conflict
            raise FolderConflictError("Folder is permanently deleted and cannot be restored.")

        if folder.parent_id:
            parent_stmt = select(Folder).where(Folder.id == folder.parent_id)
            p_result = await self.session.execute(parent_stmt)
            parent = p_result.scalar_one_or_none()
            if parent and parent.is_deleted:
                raise FolderParentDeletedError("Restore parent folder first.")
            # Also re-validate depth just in case tree moved
            if parent and parent.depth + 1 > self.MAX_DEPTH:
                raise FolderConflictError("Restoring this folder would exceed maximum depth.")

        # Redis lock
        client = get_redis_client()
        lock_key = f"lock:ws:{workspace_id}:folder:{folder_id}:cascade"
        acquired = await client.set(lock_key, "1", nx=True, px=300000)
        if not acquired:
            return "duplicate"

        folder.is_deleted = False
        folder.deleted_at = None
        folder.deleted_by_user_id = None
        folder.version += 1
        folder.purge_at = None
        folder.purge_status = None
        folder.purge_started_at = None
        folder.purge_worker_task_id = None
        
        audit_log = AuditLog(
            action="folder.restored",
            user_id=actor_id,
            resource_type="folder",
            resource_id=str(folder_id),
            details={"cascade_pending": True}
        )
        self.session.add(audit_log)
        await self.session.flush()

        from backend.tasks.folders import cascade_restore_subtree
        task = cascade_restore_subtree.delay(
            folder_id=str(folder_id),
            workspace_id=str(workspace_id),
            actor_id=str(actor_id)
        )
        audit_log.details["worker_task_id"] = task.id
        
        event = FolderRestoredEvent(workspace_id=workspace_id, folder_id=folder_id, actor_id=actor_id, cascade_pending=True)
        await self.dispatcher.publish(event)
        
        await FolderCache.invalidate_for_delete_restore(workspace_id, folder_id, folder.parent_id)
        return task.id

    async def get_folder_stats(self, workspace_id: uuid.UUID, folder_id: uuid.UUID) -> dict:
        """Get descendant folder counts and document counts."""
        folder = await self.repo.get_by_id_in_workspace(folder_id, workspace_id)
        if not folder:
            raise FolderNotFoundError("Folder not found.")
            
        descendant_ids = await self.repo.get_subtree_ids(folder_id, workspace_id)
        child_count = len([c for c in await self.repo.get_children(folder_id, workspace_id, 0, 1000)])
        
        return {
            "child_folder_count": child_count,
            "document_count": folder.document_count,
            "total_descendant_folder_count": len(descendant_ids) - 1
        }


    async def move_folder(self, workspace_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID, new_parent_id: uuid.UUID | None, expected_version: int) -> dict:
        """Move a folder to a new parent."""
        if folder_id == new_parent_id:
            raise FolderConflictError("Cannot move a folder into itself.")
            
        # 1. Acquire row locks in consistent order to prevent deadlocks
        lock_ids = [folder_id]
        if new_parent_id:
            lock_ids.append(new_parent_id)
        lock_ids.sort() # Sort by UUID for consistent ordering
        
        locked_folders = {}
        for f_id in lock_ids:
            f = await self.repo.get_folder_with_lock(f_id, workspace_id)
            if not f:
                raise FolderNotFoundError(f"Folder {f_id} not found.")
            locked_folders[f_id] = f
            
        folder = locked_folders[folder_id]
        new_parent = locked_folders[new_parent_id] if new_parent_id else None
        
        if expected_version != folder.version:
            raise FolderConflictError("Folder was updated elsewhere.", current_version=folder.version, current_name=folder.name)
            
        if folder.is_deleted:
            raise FolderConflictError("Cannot move a deleted folder.")
            
        if new_parent and new_parent.is_deleted:
            raise FolderConflictError("Cannot move into a deleted folder.")
            
        if folder.parent_id == new_parent_id:
            return {"status": "no_op"} # Already there
            
        # 2. Cycle Detection
        target_path = new_parent.path if new_parent else ""
        if target_path:
            is_cycle = await self.repo.check_cycle(target_path, folder.path)
            if is_cycle:
                raise FolderConflictError("Cannot move a folder into its own descendants.")
                
        # 3. Depth check
        subtree_height = await self.repo.get_subtree_height(folder_id, workspace_id)
        new_depth = (new_parent.depth + 1) if new_parent else 0
        if new_depth + subtree_height > self.MAX_DEPTH:
            raise FolderConflictError(f"Move would exceed max depth of {self.MAX_DEPTH}.")
            
        # 4. Name Uniqueness
        if await self.repo.exists_name_in_parent(workspace_id, new_parent_id, folder.name.strip().lower(), exclude_id=folder_id):
            raise FolderConflictError(f"A folder named '{folder.name}' already exists in the destination.")
            
        # 5. Acquire Redis Lock for cascade operations
        client = get_redis_client()
        lock_key = f"lock:ws:{workspace_id}:folder:{folder_id}:cascade"
        acquired = await client.set(lock_key, "1", nx=True, px=300000)
        if not acquired:
            return {"status": "duplicate"}
            
        # 6. Apply Phase 1 Updates
        old_parent_id = folder.parent_id
        old_path_prefix = folder.path
        
        folder.parent_id = new_parent_id
        folder.path = f"{new_parent.path}/{folder.id}" if new_parent else str(folder.id)
        depth_delta = new_depth - folder.depth
        folder.depth = new_depth
        folder.cascade_status = 'move_pending'
        folder.version += 1
        
        new_path_prefix = folder.path
        
        audit_log = AuditLog(
            action="folder.moved",
            user_id=actor_id,
            resource_type="folder",
            resource_id=str(folder_id),
            details={"old_parent_id": str(old_parent_id) if old_parent_id else None, "new_parent_id": str(new_parent_id) if new_parent_id else None}
        )
        self.session.add(audit_log)
        await self.session.flush()
        
        # Dispatch Event
        from backend.services.folder.events import FolderMovedEvent
        event = FolderMovedEvent(
            workspace_id=workspace_id, folder_id=folder_id, old_parent_id=old_parent_id, new_parent_id=new_parent_id, actor_id=actor_id, cascade_pending=True
        )
        await self.dispatcher.publish(event)
        
        # Clear Cache
        await FolderCache.invalidate_for_rename(workspace_id, folder_id, old_parent_id, [])
        await FolderCache.invalidate_for_rename(workspace_id, folder_id, new_parent_id, [])
        
        # Enqueue Phase 2
        from backend.tasks.folders import cascade_move_subtree
        task = cascade_move_subtree.delay(
            source_id=str(folder_id),
            workspace_id=str(workspace_id),
            old_path_prefix=old_path_prefix,
            new_path_prefix=new_path_prefix,
            depth_delta=depth_delta,
            actor_id=str(actor_id)
        )
        
        return {"status": "accepted", "worker_task_id": task.id, "cascade_pending": True}

    async def early_hard_delete_folder(self, workspace_id: uuid.UUID, actor_id: uuid.UUID, folder_id: uuid.UUID, confirmation_name: str) -> dict:
        """Admin action to force early hard delete of a soft-deleted folder."""
        folder = await self.repo.get_by_id_in_workspace(folder_id, workspace_id)
        if folder:
            # Active folder
            raise FolderConflictError("Folder must be soft-deleted first.")
            
        from sqlalchemy import select
        stmt = select(Folder).where(
            Folder.id == folder_id,
            Folder.workspace_id == workspace_id,
            Folder.is_deleted.is_(True)
        )
        result = await self.session.execute(stmt)
        folder = result.scalar_one_or_none()
        
        if not folder:
            raise FolderNotFoundError("Folder not found.")
            
        if folder.name != confirmation_name:
            raise FolderConflictError("Confirmation name does not match the folder name.")
            
        if folder.purge_status in ('purging', 'purged'):
            raise FolderConflictError("Folder is already being purged or is purged.")
            
        folder.purge_at = datetime.now(UTC)
        folder.purge_status = 'scheduled'
        
        await self.session.flush()
        
        # Dispatch the celery task
        from backend.tasks.folders import hard_delete_folder_subtree
        task = hard_delete_folder_subtree.delay(
            folder_id=str(folder_id),
            workspace_id=str(workspace_id)
        )
        
        return {"status": "purge_scheduled", "purge_at": "immediate", "worker_task_id": task.id}
