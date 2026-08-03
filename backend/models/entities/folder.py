"""Folder Entity Model."""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class Folder(BaseModel):
    """The core hierarchical folder entity."""

    __tablename__ = "folders"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    depth: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cascade_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    purge_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    purge_started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_worker_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Constraints
        CheckConstraint("depth <= 10", name="chk_folder_depth"),
        CheckConstraint("document_count >= 0", name="chk_folder_document_count"),
        # Indexes
        Index(
            "ix_folders_workspace_root",
            "workspace_id", "parent_id",
            postgresql_where="is_deleted = false"
        ),
        Index(
            "ix_folders_parent",
            "parent_id",
            postgresql_where="is_deleted = false"
        ),
        Index(
            "ux_folders_slug_in_parent",
            "workspace_id", "parent_id", "slug",
            unique=True,
            postgresql_where="is_deleted = false"
        ),
        Index(
            "ix_folders_deleted_at",
            "workspace_id", "deleted_at",
            postgresql_where="is_deleted = true"
        ),
        Index(
            "ix_folders_purge_scheduled",
            "workspace_id", "purge_at",
            postgresql_where="purge_status = 'scheduled' AND is_deleted = true"
        ),
    )
