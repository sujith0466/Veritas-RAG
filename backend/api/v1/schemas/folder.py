"""Folder Pydantic Schemas."""

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FolderCreateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    parent_id: uuid.UUID | None = None


class FolderRenameRequest(BaseModel):
    name: str = Field(..., max_length=255)
    version: int


class FolderResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    slug: str
    depth: int
    path: str
    document_count: int
    version: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    cascade_status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FolderSummaryResponse(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    slug: str
    document_count: int
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


class FolderBreadcrumbResponse(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class FolderStatsResponse(BaseModel):
    child_folder_count: int
    document_count: int
    total_descendant_folder_count: int


class DeletionQueuedResponse(BaseModel):
    status: str = "deletion_queued"
    folder_id: uuid.UUID
    cascade_pending: bool = True
    worker_task_id: str | None = None


class RestoreQueuedResponse(BaseModel):
    status: str = "restore_queued"
    folder_id: uuid.UUID
    cascade_pending: bool = True
    worker_task_id: str | None = None


class FolderMoveRequest(BaseModel):
    target_parent_id: uuid.UUID | None = None
    version: int

class FolderMoveResponse(BaseModel):
    status: str
    worker_task_id: str | None = None
    cascade_pending: bool

class FolderHardDeleteRequest(BaseModel):
    confirmation_name: str
    reason: str | None = None

class FolderPurgeStatusResponse(BaseModel):
    folder_id: uuid.UUID
    is_deleted: bool
    deleted_at: datetime | None = None
    purge_at: datetime | None = None
    purge_status: str | None = None
    purge_started_at: datetime | None = None
    purge_completed_at: datetime | None = None
    days_until_purge: int | None = None
