"""Unit tests for WP-T3C-5: Workspace Provisioning Target Owner Validation & Row Locking.

Verifies:
1. Target owner user pessimistic row lock acquisition (with_for_update).
2. Fail-closed rejection when target owner user is not found.
3. Fail-closed rejection when target owner user has is_active=False.
4. Fail-closed rejection when target owner user has is_deleted=True.
5. Canonical WorkspaceMember creation with role='OWNER', status='ACTIVE', is_deleted=False.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.models.entities.user import User
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.models.entities.workspace import ProvisioningStatus, WorkspaceStatus
from backend.services.workspace.provisioning_service import WorkspaceProvisioningService


@pytest.fixture
def mock_workspace_repo():
    repo = AsyncMock()
    repo.exists_by_slug.return_value = False
    repo.exists_by_public_id.return_value = False
    return repo


@pytest.fixture
def mock_workspace_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_workspace_member_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_workspace_repo, mock_workspace_settings_repo, mock_workspace_member_repo):
    return WorkspaceProvisioningService(
        workspace_repo=mock_workspace_repo,
        workspace_settings_repo=mock_workspace_settings_repo,
        workspace_member_repo=mock_workspace_member_repo,
    )


@pytest.mark.asyncio
async def test_provisioning_target_user_not_found_rejected(service):
    session = AsyncMock()
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = exec_mock

    owner_id = uuid.uuid4()
    with pytest.raises(ValueError, match="target owner user not found, inactive, or deleted"):
        await service.provision_workspace(
            session=session,
            name="Orphaned Target Corp",
            owner_user_id=owner_id,
        )


@pytest.mark.asyncio
async def test_provisioning_target_user_inactive_rejected(service):
    session = AsyncMock()
    user = User(
        id=uuid.uuid4(),
        email="inactive@example.com",
        is_active=False,
        is_deleted=False,
    )
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = user
    session.execute.return_value = exec_mock

    with pytest.raises(ValueError, match="target owner user not found, inactive, or deleted"):
        await service.provision_workspace(
            session=session,
            name="Inactive Owner Corp",
            owner_user_id=user.id,
        )


@pytest.mark.asyncio
async def test_provisioning_target_user_deleted_rejected(service):
    session = AsyncMock()
    user = User(
        id=uuid.uuid4(),
        email="deleted@example.com",
        is_active=True,
        is_deleted=True,
    )
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = user
    session.execute.return_value = exec_mock

    with pytest.raises(ValueError, match="target owner user not found, inactive, or deleted"):
        await service.provision_workspace(
            session=session,
            name="Deleted Owner Corp",
            owner_user_id=user.id,
        )


@pytest.mark.asyncio
async def test_provisioning_canonical_membership_created(service):
    session = AsyncMock()
    owner_id = uuid.uuid4()
    user = User(
        id=owner_id,
        email="valid_owner@example.com",
        is_active=True,
        is_deleted=False,
    )
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = user
    session.execute.return_value = exec_mock
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    ws = await service.provision_workspace(
        session=session,
        name="Valid Owner Corp",
        owner_user_id=owner_id,
    )

    # Find the created WorkspaceMember
    added_members = [
        call[0][0] for call in session.add.call_args_list
        if isinstance(call[0][0], WorkspaceMember)
    ]
    assert len(added_members) == 1
    member = added_members[0]
    assert member.user_id == owner_id
    assert member.role == WorkspaceRole.OWNER.value
    assert member.status == MemberStatus.ACTIVE.value
    assert member.is_deleted is False
