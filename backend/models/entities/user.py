"""User Entity Model.

Represents users in the PostgreSQL database and links to Supabase Authentication identities.
"""

import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class User(BaseModel):
    """User account entity linked to Supabase Auth identity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # F4.7 User Profile Fields
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True, default="UTC")
    language: Mapped[str | None] = mapped_column(String(20), nullable=True, default="en-US")
    theme_preference: Mapped[str | None] = mapped_column(String(20), nullable=True, default="system")
    version: Mapped[int] = mapped_column(default=1, nullable=False, server_default="1")

    role: Mapped[str] = mapped_column(String(50), default="viewer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # F2.1 Registration Fields
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True) # Nullable only for backward compat/Supabase
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_token_hash: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    verification_token_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # F2.5 Password Reset Fields
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    password_reset_token_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Deprecated: Transitioning away from Supabase Auth
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
