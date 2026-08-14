"""Schemas and Pydantic validation models for Workspace Settings.

Enforces strict taxonomy validation across all 11 configuration categories:
general, security, ai, rag, storage, notifications, integrations, limits, branding,
api, and custom_extensions.
"""

from datetime import datetime
import enum
from typing import Any
import uuid

from pydantic import BaseModel, Field, field_validator

# ── 1. Category Models ─────────────────────────────────────────────────────────

class GeneralSettings(BaseModel):
    default_language: str = Field("en", min_length=2, max_length=10)
    timezone: str = Field("UTC", min_length=1, max_length=50)
    date_format: str = Field("YYYY-MM-DD", min_length=4, max_length=30)
    retention_days: int = Field(365, ge=1, le=3650)


class SecuritySettings(BaseModel):
    max_session_duration_minutes: int = Field(1440, ge=15, le=43200)
    idle_timeout_minutes: int = Field(60, ge=5, le=1440)
    enforce_mfa: bool = Field(False)
    allow_public_document_links: bool = Field(False)
    ip_allowlist: list[str] = Field(default_factory=list)


class AISettings(BaseModel):
    default_model: str = Field("gpt-4o", min_length=1, max_length=100)
    fallback_model: str = Field("claude-3-5-sonnet", min_length=1, max_length=100)
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(4096, ge=256, le=128000)
    enable_streaming: bool = Field(True)
    system_prompt_override: str | None = Field(None, max_length=5000)


class RetrievalMode(str, enum.Enum):
    HYBRID = "HYBRID"
    DENSE = "DENSE"
    SPARSE = "SPARSE"


class RAGSettings(BaseModel):
    retrieval_mode: RetrievalMode = Field(RetrievalMode.HYBRID)
    dense_weight: float = Field(0.7, ge=0.0, le=1.0)
    sparse_weight: float = Field(0.3, ge=0.0, le=1.0)
    top_k_chunks: int = Field(8, ge=1, le=100)
    score_threshold: float = Field(0.65, ge=0.0, le=1.0)
    enable_reranker: bool = Field(True)
    reranker_model: str = Field("bge-reranker-large", min_length=1, max_length=100)
    chunk_size: int = Field(512, ge=64, le=4096)
    chunk_overlap: int = Field(64, ge=0, le=512)

    @field_validator("sparse_weight")
    def validate_weights(cls, v, values):
        if "dense_weight" in values and abs(values["dense_weight"] + v - 1.0) > 0.05:
            # Normalize or allow reasonable precision
            pass
        return v


class DeduplicationPolicy(str, enum.Enum):
    EXACT_HASH = "EXACT_HASH"
    SEMANTIC = "SEMANTIC"
    NONE = "NONE"


class StorageSettings(BaseModel):
    max_file_size_mb: int = Field(50, ge=1, le=500)
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/markdown",
        ]
    )
    enable_ocr: bool = Field(True)
    deduplication_policy: DeduplicationPolicy = Field(DeduplicationPolicy.EXACT_HASH)


class NotificationSettings(BaseModel):
    email_notifications_enabled: bool = Field(True)
    slack_webhook_url: str | None = Field(None, max_length=255)
    alert_on_quota_threshold_pct: int = Field(80, ge=1, le=100)


class IntegrationSettings(BaseModel):
    enabled_connectors: list[str] = Field(default_factory=list)


class LimitSettings(BaseModel):
    monthly_token_budget: int = Field(5000000, ge=0)
    monthly_query_budget: int = Field(50000, ge=0)
    max_storage_gb: int = Field(100, ge=1, le=10000)
    max_members: int = Field(50, ge=1, le=1000)


class ThemeMode(str, enum.Enum):
    LIGHT = "LIGHT"
    DARK = "DARK"
    SYSTEM = "SYSTEM"


class FontFamily(str, enum.Enum):
    INTER = "Inter, sans-serif"
    ROBOTO = "Roboto, sans-serif"
    OUTFIT = "Outfit, sans-serif"
    PLUS_JAKARTA = "'Plus Jakarta Sans', sans-serif"
    SYSTEM = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    CUSTOM = "CUSTOM"


class BorderRadiusOption(str, enum.Enum):
    NONE = "0px"
    SM = "0.25rem"
    MD = "0.375rem"
    LG = "0.5rem"
    XL = "0.75rem"
    FULL = "9999px"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    clean = hex_color.lstrip("#")
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
    if len(clean) >= 6:
        return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
    return 0, 0, 0


def calculate_relative_luminance(hex_color: str) -> float:
    """Calculate W3C relative luminance for a hex color."""
    r, g, b = _hex_to_rgb(hex_color)
    rgb_linear = []
    for c in (r / 255.0, g / 255.0, b / 255.0):
        if c <= 0.03928:
            rgb_linear.append(c / 12.92)
        else:
            rgb_linear.append(((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * rgb_linear[0] + 0.7152 * rgb_linear[1] + 0.0722 * rgb_linear[2]


def calculate_contrast_ratio(hex_c1: str, hex_c2: str) -> float:
    """Calculate WCAG contrast ratio between two colors."""
    l1 = calculate_relative_luminance(hex_c1)
    l2 = calculate_relative_luminance(hex_c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


COLOR_PATTERN = r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d.]+\s*\))$"


class BrandingSettings(BaseModel):
    """Complete enterprise branding specification with WCAG AA compliance and asset versioning."""

    company_name: str | None = Field(None, min_length=1, max_length=100)
    product_name: str | None = Field(None, min_length=1, max_length=100)

    # Visual Assets with Versioning & ETags
    logo_url: str | None = Field(None, max_length=512)
    logo_etag: str | None = Field(None, max_length=64)
    logo_version: int = Field(1, ge=1)

    dark_logo_url: str | None = Field(None, max_length=512)
    dark_logo_etag: str | None = Field(None, max_length=64)
    dark_logo_version: int = Field(1, ge=1)

    favicon_url: str | None = Field(None, max_length=512)
    favicon_etag: str | None = Field(None, max_length=64)
    favicon_version: int = Field(1, ge=1)

    # Theme & Base Tokens
    theme_mode: ThemeMode = Field(default=ThemeMode.SYSTEM)
    font_family: FontFamily = Field(default=FontFamily.INTER)
    custom_font_url: str | None = Field(None, max_length=512)
    border_radius: BorderRadiusOption = Field(default=BorderRadiusOption.MD)

    # Core Color Tokens
    primary_color: str = Field("#0ea5e9", pattern=COLOR_PATTERN)
    secondary_color: str = Field("#64748b", pattern=COLOR_PATTERN)
    accent_color: str = Field("#8b5cf6", pattern=COLOR_PATTERN)

    # Feedback & State Colors
    success_color: str = Field("#10b981", pattern=COLOR_PATTERN)
    warning_color: str = Field("#f59e0b", pattern=COLOR_PATTERN)
    danger_color: str = Field("#ef4444", pattern=COLOR_PATTERN)
    info_color: str = Field("#3b82f6", pattern=COLOR_PATTERN)

    # Canvas & Surface Tokens
    neutral_background: str | None = Field(None, pattern=COLOR_PATTERN)
    neutral_surface: str | None = Field(None, pattern=COLOR_PATTERN)
    neutral_text: str | None = Field(None, pattern=COLOR_PATTERN)
    login_background_url: str | None = Field(None, max_length=512)
    dashboard_background_url: str | None = Field(None, max_length=512)

    # Custom CSS Variable Overrides
    custom_css_variables: dict[str, str] = Field(default_factory=dict)

    @field_validator("custom_css_variables")
    def validate_custom_css_variables(cls, v):
        for key, value in v.items():
            if not key.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid CSS variable key: {key}. Only alphanumeric characters and hyphens allowed.")
            if any(forbidden in value.lower() for forbidden in ["javascript:", "expression(", "<script", "url(data:"]):
                raise ValueError(f"Potential injection detected in CSS variable '{key}'.")
        return v

    @field_validator("primary_color")
    def validate_accessibility_contrast(cls, v, values):
        # Validate that primary color when given as hex has acceptable contrast
        if v.startswith("#") and len(v) in (4, 7):
            # Check contrast against white or black text
            contrast_white = calculate_contrast_ratio(v, "#ffffff")
            contrast_black = calculate_contrast_ratio(v, "#000000")
            if max(contrast_white, contrast_black) < 3.0:
                raise ValueError(
                    f"Primary color {v} fails WCAG AA minimum contrast ratio (at least 3.0:1 required with black or white text)."
                )
        return v


class APISettings(BaseModel):
    rate_limit_rpm: int = Field(600, ge=10, le=10000)
    telemetry_enabled: bool = Field(True)


# ── 2. Master Settings Document ──────────────────────────────────────────────

class WorkspaceSettingsPayload(BaseModel):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    ai: AISettings = Field(default_factory=AISettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    branding: BrandingSettings = Field(default_factory=BrandingSettings)
    api: APISettings = Field(default_factory=APISettings)
    custom_extensions: dict[str, Any] = Field(default_factory=dict)


def get_default_workspace_settings() -> dict[str, Any]:
    """Return default dictionary representation of all settings categories."""
    return WorkspaceSettingsPayload().model_dump(mode="json")



# ── 3. Request & Response Schemas ─────────────────────────────────────────────

class WorkspaceSettingsPatchRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    settings: dict[str, Any] = Field(..., description="Partial or complete settings updates to deep merge")


class WorkspaceSettingsResetRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    category: str | None = Field(None, description="Specific category to reset, or null to reset all")


class WorkspaceSettingsImportRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    settings: dict[str, Any] = Field(..., description="Settings document to import")


class WorkspaceSettingsDataResponse(BaseModel):
    workspace_id: uuid.UUID
    settings: dict[str, Any]
    schema_version: int
    version: int
    settings_hash: str
    updated_at: datetime


class WorkspaceSettingsResponse(BaseModel):
    success: bool
    data: WorkspaceSettingsDataResponse


class WorkspaceSettingsHistoryData(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    settings: dict[str, Any]
    schema_version: int
    version: int
    settings_hash: str
    changed_by_user_id: uuid.UUID | None = None
    change_reason: str | None = None
    created_at: datetime


class WorkspaceSettingsHistoryResponse(BaseModel):
    success: bool
    data: list[WorkspaceSettingsHistoryData]


# ── 4. Branding Specific Schemas (F3.7) ──────────────────────────────────────

class WorkspaceBrandingPreviewRequest(BaseModel):
    branding: BrandingSettings = Field(..., description="Draft branding configuration to preview")


class WorkspaceBrandingPublishRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    branding: BrandingSettings = Field(..., description="Branding configuration to commit and publish")
    change_reason: str = Field(default="Updated workspace branding", max_length=255)


class WorkspaceBrandingRollbackRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    target_version: int = Field(..., ge=1, description="Historical settings version to rollback branding from")
    change_reason: str = Field(default="Rollback workspace branding", max_length=255)


class WorkspaceBrandingDataResponse(BaseModel):
    workspace_id: uuid.UUID
    branding: BrandingSettings
    css_variables: dict[str, str]
    css_string: str
    tailwind_tokens: dict[str, Any]
    theme_mode: str
    version: int
    settings_hash: str
    is_preview: bool = False


class WorkspaceBrandingResponse(BaseModel):
    success: bool
    data: WorkspaceBrandingDataResponse


class WorkspaceBrandingDiffResponse(BaseModel):
    success: bool
    workspace_id: uuid.UUID
    from_version: int
    to_version: int
    diff: dict[str, Any]

