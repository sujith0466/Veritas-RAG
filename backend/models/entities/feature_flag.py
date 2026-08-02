"""FeatureFlag entity model for master feature flag configurations."""

import enum
from typing import Any

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class FlagCategory(str, enum.Enum):
    """Categories for feature flags."""
    SYSTEM = "SYSTEM"
    AI = "AI"
    RAG = "RAG"
    SECURITY = "SECURITY"
    UI = "UI"
    BETA = "BETA"
    EXPERIMENTAL = "EXPERIMENTAL"
    INTERNAL = "INTERNAL"


class FlagLifecycleState(str, enum.Enum):
    """Lifecycle states for feature flags."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class FlagType(str, enum.Enum):
    """Evaluation types for feature flags."""
    BOOLEAN = "BOOLEAN"
    PERCENTAGE = "PERCENTAGE"
    TARGETING = "TARGETING"
    DATE_WINDOW = "DATE_WINDOW"
    VARIANT = "VARIANT"


class FeatureFlag(BaseModel):
    """Master entity for feature flag definitions."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default=FlagCategory.SYSTEM.value, index=True, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(50), default=FlagLifecycleState.DRAFT.value, nullable=False)
    flag_type: Mapped[str] = mapped_column(String(50), default=FlagType.BOOLEAN.value, nullable=False)
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_killswitch_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prerequisite_flag_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    default_variant_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    target_environments: Mapped[str] = mapped_column(String(255), default="production,staging,development", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
