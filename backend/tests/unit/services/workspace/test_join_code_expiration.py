"""Unit tests for Workstream E (Active Join Code Expiration Management).

Validates:
- E-01: Admin can update expiration of existing active code (7, 30, 60, 90, 365, Never)
- E-02: Code remains identical after expiration change (no regeneration, same verifier)
- E-03: Never expires (0) sets expires_at to None
- E-04: Expiration is actually enforced (expired code rejected by candidate validation)
- E-05: Valid code remains accepted before expiration
- E-06: MEMBER / VIEWER cannot change expiration (rejected)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.api.v1.schemas.workspace_onboarding import JoinCodeSettingsPatchRequest
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.join_code_service import JoinCodeService
from backend.services.workspace.management_service import (
    WorkspaceUnauthorizedError,
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
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def join_code_service(mock_settings_repo, mock_member_repo, mock_workspace_repo):
    return JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )


@pytest.mark.asyncio
async def test_active_join_code_expiration_management_e_matrix(
    mock_session,
    mock_settings_repo,
    mock_member_repo,
    mock_workspace_repo,
    join_code_service,
):
    """E-01 to E-06: Verifies post-generation expiration updates without code rotation."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()

    workspace = Workspace(
        id=workspace_id,
        name="Chronos Research Labs",
        public_id="CHRONOS-01",
        slug="chronos-research",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = workspace

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )
    member_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=member_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    mock_member_repo.get_membership = AsyncMock(return_value=admin_member)

    # 1. Generate code with 30-day initial expiration
    settings_obj = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={},
        schema_version=1,
        version=1,
        settings_hash="",
    )
    mock_settings_repo.get_by_workspace_id.return_value = settings_obj
    mock_settings_repo.get_by_workspace_id_for_update.return_value = settings_obj

    gen_resp = await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=admin_id,
        expires_in_days=30,
    )
    original_code = gen_resp.join_code
    stored_hash_before = settings_obj.settings_json["join_code"]["code_hash"]
    stored_encrypted_before = settings_obj.settings_json["join_code"]["code_encrypted"]

    # 2. E-01 & E-02: Admin updates expiration to 90 Days without changing code
    patch_req_90 = JoinCodeSettingsPatchRequest(expires_in_days=90)
    updated_settings = await join_code_service.patch_join_code_settings(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=admin_id,
        request=patch_req_90,
    )

    # Verify code hash and encrypted token remain untouched
    stored_hash_after = settings_obj.settings_json["join_code"]["code_hash"]
    stored_encrypted_after = settings_obj.settings_json["join_code"]["code_encrypted"]
    assert stored_hash_after == stored_hash_before, "Expiration update must NOT regenerate code hash"
    assert stored_encrypted_after == stored_encrypted_before, "Expiration update must NOT regenerate encrypted code"

    # Verify expiration timestamp updated to approximately 90 days from now
    assert updated_settings.expires_at is not None
    approx_90_days = datetime.now(UTC) + timedelta(days=90)
    diff = abs((updated_settings.expires_at - approx_90_days).total_seconds())
    assert diff < 60, "Expiration must be set to ~90 days in future"

    # Verify original code is still verified successfully
    is_valid, _, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session,
        workspace_id=workspace_id,
        candidate_code=original_code,
    )
    assert is_valid is True

    # 3. E-03: Admin changes expiration to Never (0)
    patch_req_never = JoinCodeSettingsPatchRequest(expires_in_days=0)
    never_settings = await join_code_service.patch_join_code_settings(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=admin_id,
        request=patch_req_never,
    )
    assert never_settings.expires_at is None
    assert settings_obj.settings_json["join_code"]["expires_at"] is None

    # Code remains valid indefinitely
    is_valid_never, _, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session,
        workspace_id=workspace_id,
        candidate_code=original_code,
    )
    assert is_valid_never is True

    # 4. E-04: Expired code enforcement
    # Artificially set expiration into past
    past_iso = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    settings_obj.settings_json["join_code"]["expires_at"] = past_iso

    is_valid_expired, err_expired, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session,
        workspace_id=workspace_id,
        candidate_code=original_code,
    )
    assert is_valid_expired is False
    assert err_expired == "Join code has expired."

    # 5. E-06: Member cannot patch expiration
    mock_member_repo.get_membership = AsyncMock(return_value=member_member)
    with pytest.raises(WorkspaceUnauthorizedError):
        await join_code_service.patch_join_code_settings(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=member_id,
            request=patch_req_90,
        )
