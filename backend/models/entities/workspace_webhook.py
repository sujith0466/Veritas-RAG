"""Workspace Webhook Entity."""

from typing import Any

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TenantAwareBaseModel


class WorkspaceWebhook(TenantAwareBaseModel):
    """Stores webhook endpoints configured by a workspace."""

    __tablename__ = "workspace_webhooks"

    endpoint_url: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    secret_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    events: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
