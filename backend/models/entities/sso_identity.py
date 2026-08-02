"""SSO Identity Entity Model.

Maps OIDC provider identities (like Google) to local RAGuard user accounts.
"""

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel
from backend.models.entities.user import User


class SSOIdentity(BaseModel):
    """Maps an external OIDC provider identity to a local User."""

    __tablename__ = "sso_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    linked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow
    )
    sso_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True) # avoiding `metadata` name collision with SQLAlchemy Base.metadata

    # Relationships
    user: Mapped[User] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<SSOIdentity(id={self.id}, user_id={self.user_id}, provider='{self.provider}')>"
