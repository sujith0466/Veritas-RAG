"""SSO Identity Provider Entities."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class IdentityProvider(BaseModel):
    """F4.9 Identity Provider Entity."""

    __tablename__ = "identity_providers"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    entity_id_issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    sso_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    logout_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    metadata_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    certificates: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    attribute_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    domain_restrictions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    jit_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    force_sso: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    version: Mapped[int] = mapped_column(Integer, server_default="1", default=1, nullable=False)
