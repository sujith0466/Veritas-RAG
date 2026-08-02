"""Domain Entities."""

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.models.base import BaseModel


class WorkspaceDomain(BaseModel):
    """F4.8 Workspace Domain Entity."""

    __tablename__ = "workspace_domains"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    domain_name: Mapped[str] = mapped_column(String(255), nullable=False)
    verification_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dns_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1, nullable=False)

class DomainCooldown(Base):
    """F4.8 Domain Cooldown Entity."""

    __tablename__ = "domain_cooldowns"

    domain_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    released_by_workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    cooldown_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
