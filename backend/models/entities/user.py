"""User Entity Model.

Represents users in the PostgreSQL database and links to Supabase Authentication identities.
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


from sqlalchemy.dialects.postgresql import JSONB

class User(BaseModel):
    """User account entity linked to Supabase Auth identity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supabase_user_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )
    workspace_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    profile_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    workspace_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}', tenant_id='{self.tenant_id}')>"
