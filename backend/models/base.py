"""Abstract Base Model for all RAGuard ORM entities.

Provides common primary key (`id`), audit timestamps (`created_at`, `updated_at`),
and soft-delete flag (`is_deleted`) to ensure schema uniformity.
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class BaseModel(Base):
    """Abstract base class for all entity models."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance column values to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
