"""Canonical Identity and Workspace Onboarding Schemas (WS-A1).

Defines the official contracts, validation rules, and DTOs for:
- 5-Way Identifier Separation (Tenant ID, Workspace ID, Workspace Slug, Join Code, Invitation Token)
- Workspace Discovery & Safe Public Preview (Mode 1, Mode 2, Mode 3)
- Workspace Joining Request
- Join Code Configuration & Ephemeral Generation Responses
- Active Workspace Context Switching Request & Response
- Onboarding Registration Context
"""

from datetime import datetime
import enum
import re
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# ── 1. Identifier Validation Constants & Regexes ─────────────────────────────

# Tenant ID: Internal RFC 4122 UUIDv4 (never a public join credential)
TENANT_UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# Workspace ID: Public, stable, human-readable identifier (e.g. 'ACME-7X92', 'WS-8K2M9P')
# Bounded 3 to 32 characters, uppercase alphanumeric and hyphens.
WORKSPACE_ID_PATTERN = r"^[A-Z0-9]{2,20}(?:-[A-Z0-9]{2,12})*$"

# Workspace Slug: Navigation/URL identifier (e.g. 'acme-ai', 'marketing-team')
# Lowercase URL-safe format, 3 to 48 characters.
WORKSPACE_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Join Code: Display format 'VR-XXXXXX', 6 Crockford base32 characters (excluding 0, O, 1, I, L)
CROCKFORD_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
JOIN_CODE_PATTERN = r"^VR-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$"

# Invitation Token: Opaque high-entropy token (e.g. 'sec_inv_...' or base64url)
INVITATION_TOKEN_PATTERN = r"^[A-Za-z0-9_\-\.]{16,128}$"


class JoiningMode(str, enum.Enum):
    """Categorical joining modality for a workspace."""
    OPEN = "OPEN"                 # Mode 1: Open Workspace ID joining (open_join=True)
    JOIN_CODE = "JOIN_CODE"       # Mode 2: Protected Workspace ID + Join Code joining
    INVITE_ONLY = "INVITE_ONLY"   # Mode 3: Invitation Token joining only


# ── 2. Workspace Preview Contracts ───────────────────────────────────────────

class WorkspacePreviewData(BaseModel):
    """Safe public metadata for workspace preview prior to joining.

    SECURITY INVARIANT:
    Exposes only public, sanitized information. NEVER exposes:
    - Internal Tenant UUID
    - Internal member lists or counts
    - Quotas or billing details
    - Join code hashes or secret configurations
    - Invitation tokens or internal URLs
    """
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(
        ...,
        description="Public, user-facing Workspace ID (e.g. 'ACME-7X92')",
    )
    workspace_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name of the workspace",
    )
    workspace_slug: str = Field(
        ...,
        min_length=3,
        max_length=48,
        description="URL navigation slug of the workspace",
    )
    joining_mode: JoiningMode = Field(
        ...,
        description="Current join policy of the workspace (OPEN, JOIN_CODE, INVITE_ONLY)",
    )
    requires_join_code: bool = Field(
        ...,
        description="Whether a valid Join Code is mandatory to enter",
    )
    open_join: bool = Field(
        ...,
        description="Whether open joining by Workspace ID alone is permitted",
    )
    require_approval: bool = Field(
        ...,
        description="Whether entering this workspace requires administrator approval",
    )
    default_join_role: str = Field(
        default="MEMBER",
        description="Default role assigned to entrants ('MEMBER', 'VIEWER')",
    )

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id_format(cls, v: str) -> str:
        clean = v.strip().upper()
        if re.match(TENANT_UUID_PATTERN, clean):
            raise ValueError("Internal Tenant UUID cannot be exposed as Workspace ID.")
        if not re.match(r"^[A-Z0-9\-]{3,32}$", clean):
            raise ValueError(f"Invalid Workspace ID format '{v}'.")
        return clean

    @field_validator("workspace_slug")
    @classmethod
    def validate_slug_format(cls, v: str) -> str:
        clean = v.strip()
        if clean != clean.lower() or not re.match(WORKSPACE_SLUG_PATTERN, clean):
            raise ValueError(f"Invalid Workspace Slug format '{v}'. Expected lowercase alphanumeric with hyphens.")
        return clean


    @field_validator("default_join_role")
    @classmethod
    def validate_default_role(cls, v: str) -> str:
        role_upper = v.strip().upper()
        if role_upper not in {"MEMBER", "VIEWER"}:
            raise ValueError("Preview join role must be a non-elevated role ('MEMBER' or 'VIEWER').")
        return role_upper


class WorkspacePreviewResponse(BaseModel):
    """Response payload for public workspace discovery and preview."""
    success: bool = True
    message: str = "Workspace preview retrieved successfully."
    data: WorkspacePreviewData


# ── 3. Join Workspace Request Contract ───────────────────────────────────────

class JoinWorkspaceRequest(BaseModel):
    """Payload for joining an existing workspace.

    SECURITY INVARIANTS:
    1. Tenant UUID is rejected as a public join credential.
    2. Frontend cannot submit a target role (prevents role elevation).
    """
    model_config = ConfigDict(extra="forbid")

    workspace_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=64,
        description="Target Workspace ID or Slug (never Tenant UUID)",
    )
    join_code: str | None = Field(
        default=None,
        description="Optional Join Code (VR-XXXXXX) for protected workspaces",
    )
    invitation_token: str | None = Field(
        default=None,
        description="Optional Invitation Token (sec_inv_*)",
    )

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_identifier(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if re.match(TENANT_UUID_PATTERN, clean):
            raise ValueError(
                "Tenant UUID cannot be used as a public join credential. "
                "Provide a valid Workspace ID or Workspace Slug."
            )
        return clean

    @field_validator("join_code")
    @classmethod
    def normalize_and_validate_join_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            raise ValueError(
                "Invalid Join Code format. Expected 'VR-XXXXXX' using Crockford alphanumeric characters."
            )
        return clean

    @field_validator("invitation_token")
    @classmethod
    def validate_invitation_token(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if not re.match(INVITATION_TOKEN_PATTERN, clean):
            raise ValueError("Invalid Invitation Token format.")
        return clean

    @model_validator(mode="after")
    def validate_join_intent_or_identifier(self) -> "JoinWorkspaceRequest":
        if not self.workspace_id and not self.invitation_token:
            raise ValueError(
                "Either 'workspace_id' or 'invitation_token' must be provided."
            )
        return self


class JoinWorkspaceData(BaseModel):
    """Data returned upon successful workspace join."""
    workspace_id: uuid.UUID = Field(..., description="Internal workspace tenant UUID")
    workspace_name: str
    role: str
    status: str = "ACTIVE"
    member_id: uuid.UUID


class JoinWorkspaceResponse(BaseModel):
    """Response payload for workspace join operation."""
    success: bool = True
    message: str = "Successfully joined workspace."
    data: JoinWorkspaceData


# ── 4. Join Code Settings & Mutation Contracts ───────────────────────────────

class JoinCodeSettingsSchema(BaseModel):
    """Configuration state for workspace join code in workspace settings.

    SECURITY INVARIANT:
    Plaintext Join Code is NEVER stored or exposed in this schema.
    Only administrative metadata and a presence indicator (`has_code`) are provided.
    """
    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Whether self-service joining via Join Code is active",
    )
    default_role: str = Field(
        default="MEMBER",
        description="Default role assigned to entrants ('MEMBER', 'VIEWER')",
    )
    require_approval: bool = Field(
        default=False,
        description="Whether join code entrants require administrator approval",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Timestamp when the current join code expires",
    )
    generated_at: datetime | None = Field(
        default=None,
        description="Timestamp when the current join code was generated",
    )
    generated_by: uuid.UUID | None = Field(
        default=None,
        description="User ID of administrator who generated the code",
    )
    has_code: bool = Field(
        default=False,
        description="Whether an active join code hash exists in settings",
    )
    max_uses: int | None = Field(
        default=None,
        description="Maximum number of times this code can be used (null for unlimited)",
    )
    current_uses: int = Field(
        default=0,
        description="Number of times this code has been used",
    )

    @field_validator("default_role")
    @classmethod
    def validate_default_role(cls, v: str) -> str:
        role_upper = v.strip().upper()
        if role_upper not in {"MEMBER", "VIEWER"}:
            raise ValueError(
                f"Join code default role must be 'MEMBER' or 'VIEWER', got '{v}'. "
                "Join codes cannot grant elevated roles ('OWNER', 'ADMIN')."
            )
        return role_upper


class JoinCodeSettingsPatchRequest(BaseModel):
    """Payload for updating join code configuration."""
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = Field(default=None, description="Enable or disable join code entry")
    default_role: str | None = Field(default=None, description="Updated default role ('MEMBER', 'VIEWER')")
    require_approval: bool | None = Field(default=None, description="Require admin approval for entrants")
    max_uses: int | None = Field(default=None, ge=1, le=10000, description="Maximum number of allowable uses")
    expires_in_days: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Updated expiration duration in days (0 for Never, 7, 30, 60, 90, 365)",
    )

    @field_validator("default_role")
    @classmethod
    def validate_default_role(cls, v: str | None) -> str | None:
        if v is None:
            return None
        role_upper = v.strip().upper()
        if role_upper not in {"MEMBER", "VIEWER"}:
            raise ValueError("Join code default role must be 'MEMBER' or 'VIEWER'.")
        return role_upper

    @field_validator("expires_in_days")
    @classmethod
    def validate_expires_in_days(cls, v: int | None) -> int | None:
        if v is not None and v not in {0, 7, 30, 60, 90, 365}:
            raise ValueError("Expiration duration must be one of: 0 (Never), 7, 30, 60, 90, 365 days.")
        return v


class WorkspaceJoinAccessResponse(BaseModel):
    """Safe authenticated read payload for workspace joining information (WS-D).

    Allows authorized workspace members (OWNER, ADMIN, MEMBER, VIEWER) to read
    the active Join Code and canonical Join Link without administrative mutation privileges.
    """
    success: bool = True
    workspace_id: uuid.UUID
    public_id: str | None = None
    workspace_name: str
    has_active_code: bool = False
    join_code: str | None = None
    join_link: str | None = None
    expires_at: datetime | None = None
    default_role: str = "MEMBER"


class JoinCodeGenerateResponse(BaseModel):
    """Ephemeral response returned strictly once upon join code generation/regeneration.

    SECURITY INVARIANT:
    Plaintext Join Code is returned in this mutation response ONLY.
    It is never persisted in plaintext anywhere in the database or cache.
    """
    success: bool = True
    join_code: str = Field(
        ...,
        description="Plaintext Join Code displayed once to the administrator (VR-XXXXXX)",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Expiration timestamp of the generated code",
    )
    default_role: str = Field(
        default="MEMBER",
        description="Default role assigned to entrants",
    )
    warning: str = Field(
        default="This Join Code will only be displayed once. Copy and share it with your team now. "
                "Veritas-RAG stores only a cryptographic hash and cannot retrieve this code later.",
        description="One-time display warning",
    )

    @field_validator("join_code")
    @classmethod
    def validate_join_code_shape(cls, v: str) -> str:
        clean = v.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            raise ValueError("Generated Join Code does not conform to 'VR-XXXXXX' format.")
        return clean


# ── 5. Active Workspace Context Switching Contracts ──────────────────────────

class SwitchWorkspaceRequest(BaseModel):
    """Payload for switching active workspace session context."""
    model_config = ConfigDict(extra="forbid")

    workspace_id: uuid.UUID | str | None = Field(
        default=None,
        description="Target workspace identifier (tenant UUID, public Workspace ID, or slug)",
    )


class SwitchWorkspaceData(BaseModel):
    """Data returned upon successful workspace context switch."""
    workspace_id: uuid.UUID = Field(..., description="Target workspace tenant UUID")
    workspace_public_id: str | None = Field(default=None, description="Public Workspace ID")
    workspace_slug: str | None = Field(default=None, description="Workspace navigation slug")
    workspace_name: str
    role: str
    access_token: str = Field(..., description="Rotated JWT access token bound to the selected workspace")
    token_type: str = "Bearer"


class SwitchWorkspaceResponse(BaseModel):
    """Response payload for workspace switching."""
    success: bool = True
    message: str = "Workspace context switched successfully."
    data: SwitchWorkspaceData


class CurrentWorkspaceData(BaseModel):
    """Active workspace session context data for the authenticated user."""
    workspace_id: uuid.UUID = Field(..., description="Active workspace internal tenant UUID")
    public_id: str | None = Field(default=None, description="Public Workspace ID")
    name: str = Field(..., description="Workspace display name")
    slug: str = Field(..., description="Workspace URL navigation slug")
    role: str = Field(..., description="Authoritative membership role in this workspace")
    status: str = Field(default="ACTIVE", description="Workspace lifecycle status")
    joined_at: datetime | None = Field(default=None, description="Timestamp when user joined workspace")
    updated_at: datetime | None = Field(default=None, description="Workspace last updated timestamp")


class CurrentWorkspaceResponse(BaseModel):
    """Response payload for current active workspace context."""
    success: bool = True
    data: CurrentWorkspaceData | None = None


class UserWorkspaceMembership(BaseModel):
    """Summary of a user's membership in an active workspace."""
    workspace_id: uuid.UUID = Field(..., description="Workspace internal tenant UUID")
    public_id: str | None = Field(default=None, description="Public Workspace ID")
    name: str = Field(..., description="Workspace display name")
    slug: str = Field(..., description="Workspace URL navigation slug")
    role: str = Field(..., description="User's role in this workspace")
    status: str = Field(default="ACTIVE", description="Membership status")
    is_active_context: bool = Field(default=False, description="Whether this workspace is the current active session context")


class UserWorkspacesListResponse(BaseModel):
    """Response payload listing all active workspaces for the calling user."""
    success: bool = True
    total: int
    items: list[UserWorkspaceMembership]


# ── 6. Onboarding Registration Context Contract ──────────────────────────────

class OnboardingContext(BaseModel):
    """Metadata describing the onboarding intent accompanying an authentication request."""
    model_config = ConfigDict(extra="forbid")

    workspace_id: str | None = Field(
        default=None,
        description="Target Workspace ID or Slug to join",
    )
    join_code: str | None = Field(
        default=None,
        description="Optional Join Code (VR-XXXXXX) for protected join",
    )
    invitation_token: str | None = Field(
        default=None,
        description="Optional Invitation Token (sec_inv_*)",
    )
    workspace_name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional workspace name when creating a new workspace",
    )

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if re.match(TENANT_UUID_PATTERN, clean):
            raise ValueError("Tenant UUID cannot be used as a public join credential.")
        return clean

    @field_validator("join_code")
    @classmethod
    def validate_join_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            raise ValueError("Invalid Join Code format. Expected 'VR-XXXXXX'.")
        return clean


# ── 7. Join Intent Contracts (WS-A5) ──────────────────────────────────────────

class JoinIntentCreateRequest(BaseModel):
    """Payload for creating a pre-authentication join intent."""
    model_config = ConfigDict(extra="forbid")

    workspace_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=64,
        description="Target Workspace ID or Slug (never Tenant UUID)",
    )
    join_code: str | None = Field(
        default=None,
        description="Optional Join Code (VR-XXXXXX)",
    )
    invitation_token: str | None = Field(
        default=None,
        description="Optional Invitation Token (sec_inv_*)",
    )

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if re.match(TENANT_UUID_PATTERN, clean):
            raise ValueError("Tenant UUID cannot be used as a public join credential.")
        return clean

    @field_validator("join_code")
    @classmethod
    def normalize_join_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            raise ValueError("Invalid Join Code format. Expected 'VR-XXXXXX'.")
        return clean

    @field_validator("invitation_token")
    @classmethod
    def validate_invitation_token(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if not re.match(INVITATION_TOKEN_PATTERN, clean):
            raise ValueError("Invalid Invitation Token format.")
        return clean

    @model_validator(mode="after")
    def check_presence(self) -> "JoinIntentCreateRequest":
        if not self.workspace_id and not self.invitation_token and not self.join_code:
            raise ValueError("At least one join credential (workspace_id, join_code, or invitation_token) must be provided.")
        return self


class JoinIntentCreateData(BaseModel):
    """Data returned upon successful join intent creation."""
    intent_id: str = Field(..., description="Opaque URL-safe token representing the join intent")
    expires_in_seconds: int = Field(default=600, description="Expiration TTL in seconds (10 minutes)")


class JoinIntentCreateResponse(BaseModel):
    """Response returned upon successful join intent creation."""
    success: bool = True
    message: str = "Join intent recorded successfully."
    data: JoinIntentCreateData


class JoinIntentPreviewData(BaseModel):
    """Safe public metadata representing a pre-auth join intent without exposing secrets."""
    model_config = ConfigDict(extra="forbid")

    intent_id: str
    workspace_id: str | None = Field(default=None, description="Public Workspace ID")
    workspace_name: str | None = Field(default=None, description="Display name of target workspace")
    workspace_slug: str | None = Field(default=None, description="URL slug of target workspace")
    joining_mode: JoiningMode = Field(..., description="Resolved joining mode (OPEN, JOIN_CODE, INVITE_ONLY)")
    requires_join_code: bool = False
    has_invitation: bool = False
    target_email_masked: str | None = Field(default=None, description="Masked recipient email if from an invitation")


class JoinIntentPreviewResponse(BaseModel):
    """Response returned upon resolving a join intent preview."""
    success: bool = True
    message: str = "Join intent preview retrieved successfully."
    data: JoinIntentPreviewData


__all__ = [
    "TENANT_UUID_PATTERN",
    "WORKSPACE_ID_PATTERN",
    "WORKSPACE_SLUG_PATTERN",
    "JOIN_CODE_PATTERN",
    "INVITATION_TOKEN_PATTERN",
    "JoiningMode",
    "WorkspacePreviewData",
    "WorkspacePreviewResponse",
    "JoinWorkspaceRequest",
    "JoinWorkspaceData",
    "JoinWorkspaceResponse",
    "JoinCodeSettingsSchema",
    "JoinCodeSettingsPatchRequest",
    "JoinCodeGenerateResponse",
    "SwitchWorkspaceRequest",
    "SwitchWorkspaceData",
    "SwitchWorkspaceResponse",
    "CurrentWorkspaceData",
    "CurrentWorkspaceResponse",
    "UserWorkspaceMembership",
    "UserWorkspacesListResponse",
    "OnboardingContext",
    "JoinIntentCreateRequest",
    "JoinIntentCreateData",
    "JoinIntentCreateResponse",
    "JoinIntentPreviewData",
    "JoinIntentPreviewResponse",
]
