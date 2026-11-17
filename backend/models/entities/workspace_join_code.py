"""Workspace Join Code & Redemption Entity Models.

Implements creator-scoped join codes with authenticated AES-256-GCM encryption,
deterministic dual-pepper HMAC-SHA256 candidate lookup hash, and immutable
redemption tracking.
"""

import datetime
from datetime import UTC
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class WorkspaceJoinCode(BaseModel):
    """Creator-scoped join code entity.
    
    Decoupled from workspace settings to allow each OWNER and ADMIN to independently
    manage active join codes for a workspace.
    """

    __tablename__ = "workspace_join_codes"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operational_custodian_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    code_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    lookup_pepper_version: Mapped[str] = mapped_column(
        String(16),
        default="v1",
        nullable=False,
    )
    encrypted_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    encryption_key_version: Mapped[str] = mapped_column(
        String(16),
        default="enc_v1",
        nullable=False,
    )
    code_display: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_legacy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    use_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    warning_3d_sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    warning_24h_sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    warning_1h_sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    warning_expired_sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace = relationship("Workspace", backref="join_codes", lazy="selectin")
    created_by = relationship("User", foreign_keys=[created_by_user_id], lazy="selectin")
    operational_custodian = relationship("User", foreign_keys=[operational_custodian_user_id], lazy="selectin")

    __table_args__ = (
        Index("idx_wjc_workspace_creator", "workspace_id", "created_by_user_id"),
        Index("idx_wjc_active_lookup", "workspace_id", "is_enabled", "expires_at"),
        Index(
            "uq_wjc_active_creator",
            "workspace_id",
            "created_by_user_id",
            unique=True,
            postgresql_where=(is_enabled.is_(True)),
        ),
    )


class WorkspaceJoinCodeRedemption(BaseModel):
    """Immutable redemption ledger for join code usage.
    
    Protected with ON DELETE RESTRICT to guarantee audit retention.
    """

    __tablename__ = "workspace_join_code_redemptions"

    join_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace_join_codes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    redeemed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    join_code = relationship("WorkspaceJoinCode", backref="redemptions", lazy="selectin")
    workspace = relationship("Workspace", lazy="selectin")
    user = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("uq_wjc_redemption", "join_code_id", "user_id", unique=True),
        Index("idx_wjcr_workspace", "workspace_id"),
        Index("idx_wjcr_user", "user_id"),
    )
