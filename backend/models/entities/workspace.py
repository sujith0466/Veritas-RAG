import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class WorkspaceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    SUSPENDED = "SUSPENDED"
    DELETING = "DELETING"
    PURGING = "PURGING"
    DELETED = "DELETED"


class ProvisioningStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    READY = "READY"
    FAILED = "FAILED"


class Workspace(BaseModel):
    """The core multi-tenant boundary entity."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=WorkspaceStatus.ACTIVE.value, nullable=False)
    provisioning_status: Mapped[str] = mapped_column(String(50), default=ProvisioningStatus.PENDING.value, nullable=False)
    suspended_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft Deletion & Retention
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deletion_reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deletion_reason_text: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Infrastructure Mapping
    storage_prefix: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    qdrant_namespace: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


