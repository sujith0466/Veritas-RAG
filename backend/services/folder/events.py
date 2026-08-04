"""Folder Domain Events."""

from dataclasses import dataclass
import uuid

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


@dataclass(kw_only=True, frozen=True)
class FolderCreatedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    actor_id: uuid.UUID
    event_type: EventType = EventType.FOLDER_CREATED


@dataclass(kw_only=True, frozen=True)
class FolderRenamedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    old_name: str
    new_name: str
    actor_id: uuid.UUID
    event_type: EventType = EventType.FOLDER_RENAMED


@dataclass(kw_only=True, frozen=True)
class FolderSoftDeletedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    actor_id: uuid.UUID
    cascade_pending: bool
    event_type: EventType = EventType.FOLDER_SOFT_DELETED


@dataclass(kw_only=True, frozen=True)
class FolderRestoredEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    actor_id: uuid.UUID
    cascade_pending: bool
    event_type: EventType = EventType.FOLDER_RESTORED


@dataclass(kw_only=True, frozen=True)
class FolderChildrenSoftDeletedEvent(BaseEvent):
    workspace_id: uuid.UUID
    root_folder_id: uuid.UUID
    deleted_count: int
    worker_task_id: str
    event_type: EventType = EventType.FOLDER_CHILDREN_SOFT_DELETED


@dataclass(kw_only=True, frozen=True)
class FolderChildrenRestoredEvent(BaseEvent):
    workspace_id: uuid.UUID
    root_folder_id: uuid.UUID
    restored_count: int
    worker_task_id: str
    event_type: EventType = EventType.FOLDER_CHILDREN_RESTORED


@dataclass(kw_only=True, frozen=True)
class FolderMovedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    old_parent_id: uuid.UUID | None
    new_parent_id: uuid.UUID | None
    actor_id: uuid.UUID
    cascade_pending: bool
    event_type: EventType = EventType.FOLDER_MOVED


@dataclass(kw_only=True, frozen=True)
class FolderSubtreeMovedEvent(BaseEvent):
    workspace_id: uuid.UUID
    root_folder_id: uuid.UUID
    moved_count: int
    worker_task_id: str
    event_type: EventType = EventType.FOLDER_SUBTREE_MOVED


@dataclass(kw_only=True, frozen=True)
class FolderPurgeStartedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    actor_id: uuid.UUID
    subtree_folder_count: int
    event_type: EventType = EventType.FOLDER_PURGE_STARTED


@dataclass(kw_only=True, frozen=True)
class FolderHardDeletedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    documents_deleted: int
    vectors_deleted: int
    s3_objects_deleted: int
    folders_deleted: int
    event_type: EventType = EventType.FOLDER_HARD_DELETED


@dataclass(kw_only=True, frozen=True)
class FolderPurgeFailedEvent(BaseEvent):
    workspace_id: uuid.UUID
    folder_id: uuid.UUID
    error: str
    retry_count: int
    event_type: EventType = EventType.FOLDER_PURGE_FAILED
