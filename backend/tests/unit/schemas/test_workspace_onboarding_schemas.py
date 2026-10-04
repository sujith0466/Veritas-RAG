"""Unit tests for WS-A1: Contracts, Schemas & Identifier Definitions.

Tests all 12 required verification areas:
1. Workspace Preview validation
2. Workspace ID format validation
3. Workspace Slug validation
4. Join Code format validation
5. Join Code normalization
6. Invitation Token contract
7. Join Workspace request
8. Switch Workspace request
9. Registration context validation
10. Invalid role/elevation attempts
11. Sensitive-field exclusion (no leakage of Tenant UUID, hashes, quotas, secrets)
12. Backward compatibility of existing auth/registration contracts
"""

from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

from backend.api.v1.schemas.registration import RegistrationRequest
from backend.api.v1.schemas.workspace_onboarding import (
    INVITATION_TOKEN_PATTERN,
    JOIN_CODE_PATTERN,
    TENANT_UUID_PATTERN,
    WORKSPACE_ID_PATTERN,
    WORKSPACE_SLUG_PATTERN,
    JoinCodeGenerateResponse,
    JoinCodeSettingsPatchRequest,
    JoinCodeSettingsSchema,
    JoiningMode,
    JoinWorkspaceData,
    JoinWorkspaceRequest,
    JoinWorkspaceResponse,
    OnboardingContext,
    SwitchWorkspaceData,
    SwitchWorkspaceRequest,
    SwitchWorkspaceResponse,
    WorkspacePreviewData,
    WorkspacePreviewResponse,
)


# ── 1. Workspace Preview Validation ──────────────────────────────────────────

def test_workspace_preview_valid():
    """Verify valid workspace preview DTO creation."""
    preview = WorkspacePreviewData(
        workspace_id="ACME-7X92",
        workspace_name="Acme Corporation",
        workspace_slug="acme-corp",
        joining_mode=JoiningMode.OPEN,
        requires_join_code=False,
        open_join=True,
        require_approval=False,
        default_join_role="MEMBER",
    )
    assert preview.workspace_id == "ACME-7X92"
    assert preview.workspace_name == "Acme Corporation"
    assert preview.workspace_slug == "acme-corp"
    assert preview.joining_mode == JoiningMode.OPEN
    assert preview.requires_join_code is False
    assert preview.open_join is True
    assert preview.default_join_role == "MEMBER"

    response = WorkspacePreviewResponse(data=preview)
    assert response.success is True
    assert response.data.workspace_id == "ACME-7X92"


def test_workspace_preview_mode_join_code():
    """Verify preview with protected Join Code mode."""
    preview = WorkspacePreviewData(
        workspace_id="VR-ALPHA",
        workspace_name="Alpha Team",
        workspace_slug="alpha-team",
        joining_mode=JoiningMode.JOIN_CODE,
        requires_join_code=True,
        open_join=False,
        require_approval=False,
        default_join_role="MEMBER",
    )
    assert preview.joining_mode == JoiningMode.JOIN_CODE
    assert preview.requires_join_code is True


# ── 2. Workspace ID Format Validation ────────────────────────────────────────

@pytest.mark.parametrize(
    "valid_id",
    [
        "ACME-7X92",
        "WS-8K2M9P",
        "TEAM-ENG",
        "VERITAS-CORP-01",
        "ORG123",
    ],
)
def test_workspace_id_valid_formats(valid_id):
    """Valid Workspace IDs must pass schema validation."""
    data = WorkspacePreviewData(
        workspace_id=valid_id,
        workspace_name="Test Org",
        workspace_slug="test-org",
        joining_mode=JoiningMode.OPEN,
        requires_join_code=False,
        open_join=True,
        require_approval=False,
    )
    assert data.workspace_id == valid_id.upper()


def test_workspace_id_rejects_tenant_uuid():
    """Workspace ID must NEVER accept internal Tenant UUIDs."""
    raw_uuid = str(uuid.uuid4())
    with pytest.raises(ValidationError) as exc_info:
        WorkspacePreviewData(
            workspace_id=raw_uuid,
            workspace_name="Test Org",
            workspace_slug="test-org",
            joining_mode=JoiningMode.OPEN,
            requires_join_code=False,
            open_join=True,
            require_approval=False,
        )
    assert "Tenant UUID cannot be exposed as Workspace ID" in str(exc_info.value)


# ── 3. Workspace Slug Validation ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "valid_slug",
    [
        "acme-ai",
        "marketing-team",
        "platform-core",
        "eng-v2",
    ],
)
def test_workspace_slug_valid(valid_slug):
    """Workspace slug must be lowercase and URL-safe."""
    data = WorkspacePreviewData(
        workspace_id="ACME-01",
        workspace_name="Acme",
        workspace_slug=valid_slug,
        joining_mode=JoiningMode.OPEN,
        requires_join_code=False,
        open_join=True,
        require_approval=False,
    )
    assert data.workspace_slug == valid_slug


@pytest.mark.parametrize(
    "invalid_slug",
    [
        "Acme-AI",          # uppercase
        "acme_corp",        # underscore
        "acme corp",        # whitespace
        "acme!",            # special char
        "a",                # too short (<3)
    ],
)
def test_workspace_slug_invalid(invalid_slug):
    """Invalid slug characters must be rejected."""
    with pytest.raises(ValidationError):
        WorkspacePreviewData(
            workspace_id="ACME-01",
            workspace_name="Acme",
            workspace_slug=invalid_slug,
            joining_mode=JoiningMode.OPEN,
            requires_join_code=False,
            open_join=True,
            require_approval=False,
        )


# ── 4. Join Code Format Validation ───────────────────────────────────────────

@pytest.mark.parametrize(
    "valid_code",
    [
        "VR-7K9M2P",
        "VR-234567",
        "VR-ABCDEF",
        "VR-XYZ892",
    ],
)
def test_join_code_format_valid(valid_code):
    """Valid VR-XXXXXX Crockford codes must be accepted."""
    req = JoinWorkspaceRequest(
        workspace_id="ACME-CORP",
        join_code=valid_code,
    )
    assert req.join_code == valid_code


@pytest.mark.parametrize(
    "invalid_code",
    [
        "VR-000000",        # '0' is excluded from Crockford alphabet
        "VR-OOOOOO",        # 'O' is excluded
        "VR-111111",        # '1' is excluded
        "VR-IIIIII",        # 'I' is excluded
        "VR-LLLLLL",        # 'L' is excluded
        "7K9M2P",           # missing VR- prefix
        "VR-7K9M2",         # too short (5 chars)
        "VR-7K9M2P9",       # too long (7 chars)
        "INVALID-CODE",     # wrong prefix/length
    ],
)
def test_join_code_format_invalid(invalid_code):
    """Invalid Join Code formats and ambiguous characters must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        JoinWorkspaceRequest(
            workspace_id="ACME-CORP",
            join_code=invalid_code,
        )
    assert "Invalid Join Code format" in str(exc_info.value)


# ── 5. Join Code Normalization ───────────────────────────────────────────────

def test_join_code_case_normalization():
    """Join Code input must normalize lowercase to uppercase automatically."""
    req = JoinWorkspaceRequest(
        workspace_id="ACME-CORP",
        join_code="vr-7k9m2p",
    )
    assert req.join_code == "VR-7K9M2P"


# ── 6. Invitation Token Contract ─────────────────────────────────────────────

def test_invitation_token_valid():
    """Valid opaque invitation token must be accepted."""
    token = "sec_inv_a8f9b2c3d4e5f67890123456"
    req = JoinWorkspaceRequest(
        workspace_id="ACME-CORP",
        invitation_token=token,
    )
    assert req.invitation_token == token


def test_invitation_token_too_short():
    """Invitation tokens shorter than 16 chars must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        JoinWorkspaceRequest(
            workspace_id="ACME-CORP",
            invitation_token="short_token",
        )
    assert "Invalid Invitation Token format" in str(exc_info.value)


# ── 7. Join Workspace Request ────────────────────────────────────────────────

def test_join_workspace_request_mode1_open():
    """Mode 1: Open join requires only Workspace ID."""
    req = JoinWorkspaceRequest(workspace_id="OPEN-COMMUNITY")
    assert req.workspace_id == "OPEN-COMMUNITY"
    assert req.join_code is None
    assert req.invitation_token is None


def test_join_workspace_request_mode2_protected():
    """Mode 2: Protected join requires Workspace ID and Join Code."""
    req = JoinWorkspaceRequest(
        workspace_id="ACME-AI",
        join_code="VR-8K2M9P",
    )
    assert req.workspace_id == "ACME-AI"
    assert req.join_code == "VR-8K2M9P"


def test_join_workspace_request_rejects_raw_tenant_uuid():
    """Join request MUST NOT accept a raw Tenant UUID as public join identifier."""
    raw_uuid = str(uuid.uuid4())
    with pytest.raises(ValidationError) as exc_info:
        JoinWorkspaceRequest(workspace_id=raw_uuid)
    assert "Tenant UUID cannot be used as a public join credential" in str(exc_info.value)


# ── 8. Switch Workspace Request ──────────────────────────────────────────────

def test_switch_workspace_request_valid():
    """Switch request accepts internal tenant UUID for authenticated context switch."""
    target_uuid = uuid.uuid4()
    req = SwitchWorkspaceRequest(workspace_id=target_uuid)
    assert req.workspace_id == target_uuid

    data = SwitchWorkspaceData(
        workspace_id=target_uuid,
        workspace_name="Engineering Org",
        role="MEMBER",
        access_token="fake.jwt.token",
    )
    res = SwitchWorkspaceResponse(data=data)
    assert res.success is True
    assert res.data.workspace_id == target_uuid


# ── 9. Registration Context Validation ───────────────────────────────────────

def test_registration_request_with_onboarding_context():
    """RegistrationRequest cleanly parses optional onboarding context."""
    req = RegistrationRequest(
        email="newuser@example.com",
        password="SecurePassword123!",
        full_name="Alice Smith",
        workspace_id="ACME-CORP",
        join_code="VR-7K9M2P",
        workspace_name="New Workspace Name",
    )
    assert req.email == "newuser@example.com"
    assert req.workspace_id == "ACME-CORP"
    assert req.join_code == "VR-7K9M2P"
    assert req.workspace_name == "New Workspace Name"


def test_registration_request_rejects_uuid_workspace_id():
    """RegistrationRequest rejects raw Tenant UUID in workspace_id."""
    with pytest.raises(ValidationError) as exc_info:
        RegistrationRequest(
            email="test@example.com",
            password="SecurePassword123!",
            workspace_id=str(uuid.uuid4()),
        )
    assert "Tenant UUID cannot be used as a public join credential" in str(exc_info.value)


# ── 10. Invalid Role / Elevation Attempts ────────────────────────────────────

def test_join_workspace_request_forbids_role_field():
    """JoinWorkspaceRequest forbids arbitrary extra fields like 'role'."""
    with pytest.raises(ValidationError):
        JoinWorkspaceRequest.model_validate(
            {
                "workspace_id": "ACME-CORP",
                "role": "OWNER",  # Elevation attempt
            }
        )


def test_join_code_settings_forbids_elevated_default_role():
    """JoinCodeSettingsSchema forbids setting default_role to OWNER or ADMIN."""
    with pytest.raises(ValidationError) as exc_info:
        JoinCodeSettingsSchema(
            enabled=True,
            default_role="OWNER",
        )
    assert "Join code default role must be 'MEMBER' or 'VIEWER'" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info_admin:
        JoinCodeSettingsSchema(
            enabled=True,
            default_role="ADMIN",
        )
    assert "Join code default role must be 'MEMBER' or 'VIEWER'" in str(exc_info_admin.value)


# ── 11. Sensitive-Field Exclusion ────────────────────────────────────────────

def test_workspace_preview_excludes_sensitive_fields():
    """WorkspacePreviewData forbids extra sensitive fields like tenant UUID or hashes."""
    preview_dict = {
        "workspace_id": "ACME-7X92",
        "workspace_name": "Acme",
        "workspace_slug": "acme",
        "joining_mode": "OPEN",
        "requires_join_code": False,
        "open_join": True,
        "require_approval": False,
        "default_join_role": "MEMBER",
        # Sensitive injection attempt:
        "tenant_id": str(uuid.uuid4()),
        "code_hash": "sha256:abcd",
    }
    with pytest.raises(ValidationError):
        WorkspacePreviewData.model_validate(preview_dict)


def test_join_code_settings_excludes_plaintext_and_hash():
    """JoinCodeSettingsSchema forbids plaintext code or hash injection."""
    with pytest.raises(ValidationError):
        JoinCodeSettingsSchema.model_validate(
            {
                "enabled": True,
                "join_code": "VR-7K9M2P",  # Plaintext leakage attempt
            }
        )
    with pytest.raises(ValidationError):
        JoinCodeSettingsSchema.model_validate(
            {
                "enabled": True,
                "code_hash": "sha256:e3b0c44298fc...",  # Hash leakage attempt
            }
        )


def test_join_code_generate_response_contains_one_time_warning():
    """JoinCodeGenerateResponse contains one-time plaintext and security warning."""
    res = JoinCodeGenerateResponse(
        join_code="VR-7K9M2P",
        expires_at=datetime.now(timezone.utc),
        default_role="MEMBER",
    )
    assert res.join_code == "VR-7K9M2P"
    assert "stores only a cryptographic hash" in res.warning


# ── 12. Backward Compatibility ───────────────────────────────────────────────

def test_registration_request_backward_compatible():
    """Existing native registration payloads without onboarding context remain 100% valid."""
    legacy_payload = {
        "email": "legacy@example.com",
        "password": "ValidPassword123!",
        "full_name": "Legacy User",
    }
    req = RegistrationRequest.model_validate(legacy_payload)
    assert req.email == "legacy@example.com"
    assert req.workspace_id is None
    assert req.join_code is None
    assert req.invitation_token is None


def test_registration_request_legacy_company_name_compatible():
    """RegistrationRequest accepts legacy optional company_name and workspace_name."""
    legacy_payload = {
        "email": "legacy_corp@example.com",
        "password": "ValidPassword123!",
        "full_name": "Corp User",
        "workspace_name": "Test Org",
        "company_name": "Test Company",
    }
    req = RegistrationRequest.model_validate(legacy_payload)
    assert req.workspace_name == "Test Org"
    assert req.company_name == "Test Company"
