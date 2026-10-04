"""Unit tests for WS-A3 Join Code Architecture, Hashing & Settings Persistence.

Validates all 23 Phase 16 criteria:
- Crockford Base32 format and entropy
- SHA-256 cryptographic hashing & constant-time verification
- Hash-only persistence and zero plaintext leakage
- Expiration and usage limit enforcement
- Role restriction (MEMBER/VIEWER only)
- RBAC enforcement (OWNER/ADMIN only)
- Redis cache invalidation
- Audit logging
- Cross-tenant isolation
"""

from datetime import UTC, datetime, timedelta
import re
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.api.v1.schemas.workspace_onboarding import (
    CROCKFORD_ALPHABET,
    JOIN_CODE_PATTERN,
    JoinCodeSettingsPatchRequest,
)
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.management_service import (
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)
from backend.services.workspace.join_code_service import (
    JoinCodeService,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_settings_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_member_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_workspace_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def join_code_service(mock_settings_repo, mock_member_repo, mock_workspace_repo):
    return JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )


# ==============================================================================
# 1. Format, Entropy, Hashing, and Verification
# ==============================================================================

def test_generate_plaintext_code_format(join_code_service):
    """Criterion 1: format matches ^VR-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$."""
    pattern = re.compile(f"^{JOIN_CODE_PATTERN}$")
    generated_set = set()
    for _ in range(50):
        code = join_code_service.generate_plaintext_code()
        assert pattern.match(code), f"Code {code} does not match regex"
        assert code.startswith("VR-")
        random_part = code[3:]
        assert len(random_part) == 6
        assert all(c in CROCKFORD_ALPHABET for c in random_part)
        generated_set.add(code)
    # Entropy check: all 50 generated codes are distinct
    assert len(generated_set) == 50


def test_hash_join_code_sha256(join_code_service):
    """Criterion 2: produces 64-character SHA-256 hex digest."""
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)
    assert len(code_hash) == 64
    assert re.match(r"^[a-f0-9]{64}$", code_hash)


def test_verify_join_code_match(join_code_service):
    """Criterion 3: Plaintext matches hash via verify_join_code."""
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)
    assert join_code_service.verify_join_code(code, code_hash) is True
    # Case insensitive verification
    assert join_code_service.verify_join_code("vr-9k2m4p", code_hash) is True


def test_verify_join_code_tampered_fails(join_code_service):
    """Criterion 4: Tampered or wrong code fails verify_join_code."""
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)
    assert join_code_service.verify_join_code("VR-9K2M4Q", code_hash) is False
    assert join_code_service.verify_join_code("INVALID", code_hash) is False
    assert join_code_service.verify_join_code("", code_hash) is False


def test_verify_join_code_constant_time(join_code_service):
    """Criterion 5: Uses constant-time hmac.compare_digest."""
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)
    with patch("hmac.compare_digest", wraps=__import__("hmac").compare_digest) as mock_compare:
        result = join_code_service.verify_join_code(code, code_hash)
        assert result is True
        mock_compare.assert_called_once()


# ==============================================================================
# 2. Settings Retrieval & Plaintext Leakage Prevention
# ==============================================================================

@pytest.mark.asyncio
async def test_get_join_code_settings_safe_metadata(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Criteria 6 & 7: Returns safe metadata; NEVER exposes hash or plaintext."""
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=actor_id, role="OWNER"
    )

    now_iso = datetime.now(UTC).isoformat()
    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": "a" * 64,
                "default_role": "MEMBER",
                "require_approval": True,
                "expires_at": now_iso,
                "generated_at": now_iso,
                "generated_by": str(actor_id),
                "max_uses": 50,
                "current_uses": 5,
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    settings = await join_code_service.get_join_code_settings(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=actor_id,
    )

    assert settings.enabled is True
    assert settings.default_role == "MEMBER"
    assert settings.require_approval is True
    assert settings.has_code is True
    assert settings.max_uses == 50
    assert settings.current_uses == 5
    assert settings.generated_by == actor_id

    # Verify no hash or plaintext exists in returned model
    dumped = settings.model_dump()
    assert "code_hash" not in dumped
    assert "join_code" not in dumped
    assert "code" not in dumped


# ==============================================================================
# 3. Generation, Reveal Once & Regeneration
# ==============================================================================

@pytest.mark.asyncio
async def test_generate_new_join_code_reveal_once(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Criteria 8, 9, 20, 21: Returns plaintext strictly once, logs audit, clears cache."""
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=actor_id, role="ADMIN"
    )

    initial_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={},
        version=1,
    )
    mock_settings_repo.get_by_workspace_id_for_update.return_value = initial_settings

    # Mock Redis client
    mock_redis = AsyncMock()
    with patch("backend.cache.client.get_redis_client", return_value=mock_redis):
        response = await join_code_service.generate_new_join_code(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=actor_id,
            expires_in_days=14,
            default_role="MEMBER",
            require_approval=False,
            max_uses=100,
        )

    # 1. Plaintext returned strictly in response
    assert response.join_code.startswith("VR-")
    assert response.default_role == "MEMBER"
    assert "cryptographic hash" in response.warning

    # 2. Plaintext NOT saved in DB model - only hash
    stored_join_config = initial_settings.settings_json["join_code"]
    assert "join_code" not in stored_join_config
    assert stored_join_config["code_hash"] == join_code_service.hash_join_code(response.join_code)
    assert stored_join_config["is_enabled"] is True
    assert stored_join_config["max_uses"] == 100
    assert stored_join_config["current_uses"] == 0

    # 3. Redis cache invalidated
    mock_redis.delete.assert_called_once_with(f"workspace:{workspace_id}:settings")

    # 4. Audit log created
    added_objs = [call[0][0] for call in mock_session.add.call_args_list]
    audit_logs = [obj for obj in added_objs if isinstance(obj, AuditLog)]
    assert len(audit_logs) >= 1
    gen_audit = audit_logs[0]
    assert gen_audit.action == "JOIN_CODE_GENERATED"
    assert "code" not in gen_audit.details
    assert "code_hash" not in gen_audit.details


@pytest.mark.asyncio
async def test_regenerate_join_code_invalidates_previous(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Criteria 10 & 22: Regeneration invalidates previous code immediately."""
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=actor_id, role="OWNER"
    )

    old_code = "VR-234567"
    old_hash = join_code_service.hash_join_code(old_code)

    initial_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": old_hash,
                "default_role": "VIEWER",
                "require_approval": True,
                "max_uses": 20,
                "current_uses": 10,
            }
        },
        version=2,
    )
    mock_settings_repo.get_by_workspace_id_for_update.return_value = initial_settings

    mock_redis = AsyncMock()
    with patch("backend.cache.client.get_redis_client", return_value=mock_redis):
        response = await join_code_service.generate_new_join_code(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=actor_id,
            expires_in_days=7,
            max_uses=50,
            is_regeneration=True,
        )

    new_code = response.join_code
    assert new_code != old_code

    new_join_config = initial_settings.settings_json["join_code"]
    assert new_join_config["code_hash"] != old_hash
    assert join_code_service.verify_join_code(old_code, new_join_config["code_hash"]) is False
    assert join_code_service.verify_join_code(new_code, new_join_config["code_hash"]) is True

    # Usage counter was reset
    assert new_join_config["current_uses"] == 0
    assert new_join_config["max_uses"] == 50

    # Audit logged for REGENERATED
    added_objs = [call[0][0] for call in mock_session.add.call_args_list]
    audit_logs = [obj for obj in added_objs if isinstance(obj, AuditLog)]
    assert any(log.action == "JOIN_CODE_REGENERATED" for log in audit_logs)


# ==============================================================================
# 4. Settings Patch & Audit
# ==============================================================================

@pytest.mark.asyncio
async def test_patch_join_code_settings(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Criteria 20 & 23: Patch settings updates config, logs audit, clears cache."""
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=actor_id, role="OWNER"
    )

    settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": "x" * 64,
                "default_role": "MEMBER",
                "require_approval": False,
                "max_uses": None,
                "current_uses": 3,
            }
        },
        version=1,
    )
    mock_settings_repo.get_by_workspace_id_for_update.return_value = settings
    mock_settings_repo.get_by_workspace_id.return_value = settings

    patch_req = JoinCodeSettingsPatchRequest(
        enabled=False,
        default_role="VIEWER",
        require_approval=True,
        max_uses=25,
    )

    mock_redis = AsyncMock()
    with patch("backend.cache.client.get_redis_client", return_value=mock_redis):
        res = await join_code_service.patch_join_code_settings(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=actor_id,
            request=patch_req,
        )

    assert res.enabled is False
    assert res.default_role == "VIEWER"
    assert res.require_approval is True
    assert res.max_uses == 25
    assert res.current_uses == 3

    mock_redis.delete.assert_called_once_with(f"workspace:{workspace_id}:settings")

    added_objs = [call[0][0] for call in mock_session.add.call_args_list]
    audit_logs = [obj for obj in added_objs if isinstance(obj, AuditLog)]
    assert any(log.action == "JOIN_CODE_SETTINGS_UPDATED" for log in audit_logs)


# ==============================================================================
# 5. Validation Criteria (Expiration, Disabled, Max Uses)
# ==============================================================================

@pytest.mark.asyncio
async def test_validate_join_code_candidate_valid(join_code_service, mock_session, mock_settings_repo):
    """Criterion 14: Valid code within expiration and usage limits passes."""
    workspace_id = uuid.uuid4()
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)
    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()

    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": code_hash,
                "expires_at": future,
                "max_uses": 10,
                "current_uses": 2,
                "default_role": "MEMBER",
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    valid, err, role = await join_code_service.validate_join_code_candidate(
        session=mock_session, workspace_id=workspace_id, candidate_code=code
    )
    assert valid is True
    assert err is None
    assert role == "MEMBER"


@pytest.mark.asyncio
async def test_validate_join_code_candidate_expired(join_code_service, mock_session, mock_settings_repo):
    """Criterion 11: Expired code fails validation."""
    workspace_id = uuid.uuid4()
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": code_hash,
                "expires_at": past,
                "max_uses": 10,
                "current_uses": 2,
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    valid, err, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session, workspace_id=workspace_id, candidate_code=code
    )
    assert valid is False
    assert "expired" in err.lower()


@pytest.mark.asyncio
async def test_validate_join_code_candidate_disabled(join_code_service, mock_session, mock_settings_repo):
    """Criterion 12: Disabled settings fails validation."""
    workspace_id = uuid.uuid4()
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)

    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": False,
                "code_hash": code_hash,
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    valid, err, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session, workspace_id=workspace_id, candidate_code=code
    )
    assert valid is False
    assert "disabled" in err.lower()


@pytest.mark.asyncio
async def test_validate_join_code_candidate_max_uses_reached(join_code_service, mock_session, mock_settings_repo):
    """Criterion 13: max_uses limit reached fails validation."""
    workspace_id = uuid.uuid4()
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)

    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": code_hash,
                "max_uses": 5,
                "current_uses": 5,
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    valid, err, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session, workspace_id=workspace_id, candidate_code=code
    )
    assert valid is False
    assert "usage limit" in err.lower()


@pytest.mark.asyncio
async def test_validate_join_code_candidate_wrong_code(join_code_service, mock_session, mock_settings_repo):
    """Candidate with wrong code fails validation."""
    workspace_id = uuid.uuid4()
    code = "VR-9K2M4P"
    code_hash = join_code_service.hash_join_code(code)

    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": code_hash,
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    valid, err, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session, workspace_id=workspace_id, candidate_code="VR-333333"
    )
    assert valid is False
    assert "invalid join code" in err.lower()


# ==============================================================================
# 6. RBAC & Role Restrictions
# ==============================================================================

@pytest.mark.asyncio
async def test_non_admin_cannot_access_or_generate_join_code(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Criteria 15 & 16: MEMBER or VIEWER cannot view or generate join code."""
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=actor_id, role="MEMBER"
    )

    with pytest.raises(WorkspaceUnauthorizedError):
        await join_code_service.get_join_code_settings(mock_session, workspace_id, actor_id)

    with pytest.raises(WorkspaceUnauthorizedError):
        await join_code_service.generate_new_join_code(mock_session, workspace_id, actor_id)

    with pytest.raises(WorkspaceUnauthorizedError):
        await join_code_service.patch_join_code_settings(
            mock_session, workspace_id, actor_id, JoinCodeSettingsPatchRequest(enabled=True)
        )


@pytest.mark.asyncio
async def test_owner_and_admin_authorized(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Criterion 17: OWNER and ADMIN are authorized."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=workspace_id, settings_json={"join_code": {}}
    )

    # Test OWNER
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_id, role="OWNER"
    )
    settings_owner = await join_code_service.get_join_code_settings(mock_session, workspace_id, owner_id)
    assert settings_owner is not None

    # Test ADMIN
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=admin_id, role="ADMIN"
    )
    settings_admin = await join_code_service.get_join_code_settings(mock_session, workspace_id, admin_id)
    assert settings_admin is not None


@pytest.mark.asyncio
async def test_reject_elevated_role_in_join_code(
    join_code_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Criterion 18: default_role cannot be OWNER or ADMIN."""
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=actor_id, role="OWNER"
    )

    with pytest.raises(ValueError, match="Default role must be 'MEMBER' or 'VIEWER'"):
        await join_code_service.generate_new_join_code(
            mock_session,
            workspace_id=workspace_id,
            user_id=actor_id,
            default_role="OWNER",
        )

    with pytest.raises(ValueError, match="Default role must be 'MEMBER' or 'VIEWER'"):
        await join_code_service.generate_new_join_code(
            mock_session,
            workspace_id=workspace_id,
            user_id=actor_id,
            default_role="ADMIN",
        )


# ==============================================================================
# 7. Cross-Tenant Isolation
# ==============================================================================

@pytest.mark.asyncio
async def test_cross_tenant_isolation(join_code_service, mock_session, mock_settings_repo):
    """Criterion 19: Join code generated for Tenant A cannot be used to join Tenant B."""
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    tenant_a_code = join_code_service.generate_plaintext_code()

    tenant_b_code = join_code_service.generate_plaintext_code()
    tenant_b_hash = join_code_service.hash_join_code(tenant_b_code)

    mock_settings_b = WorkspaceSettings(
        workspace_id=tenant_b_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": tenant_b_hash,
            }
        },
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings_b

    # Tenant A code submitted against Tenant B's workspace fails
    valid, err, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session, workspace_id=tenant_b_id, candidate_code=tenant_a_code
    )
    assert valid is False
    assert "invalid join code" in err.lower()
