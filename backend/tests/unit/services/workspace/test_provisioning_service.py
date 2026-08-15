from unittest.mock import MagicMock, patch, AsyncMock
import uuid

import pytest

from backend.models.entities.workspace import ProvisioningStatus, WorkspaceStatus
from backend.services.workspace.provisioning_service import WorkspaceProvisioningService


@pytest.fixture
def mock_workspace_repo():
    repo = AsyncMock()
    # By default, no collision
    repo.exists_by_slug.return_value = False
    return repo


@pytest.fixture
def mock_workspace_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_workspace_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def service(mock_workspace_repo, mock_workspace_settings_repo, mock_workspace_member_repo):
    return WorkspaceProvisioningService(
        workspace_repo=mock_workspace_repo,
        workspace_settings_repo=mock_workspace_settings_repo,
        workspace_member_repo=mock_workspace_member_repo,
    )


@pytest.mark.asyncio
async def test_provision_workspace_success(service, mock_session, mock_workspace_repo):
    owner_id = uuid.uuid4()

    workspace = await service.provision_workspace(
        session=mock_session,
        name="Test Corp",
        description="A test workspace",
        owner_user_id=owner_id
    )

    # Check slug generation
    assert workspace.slug == "test-corp"
    assert workspace.name == "Test Corp"
    assert workspace.status == WorkspaceStatus.ACTIVE.value
    assert workspace.provisioning_status == ProvisioningStatus.READY.value

    # Check DB session interactions
    assert mock_session.add.call_count == 4  # Workspace, Settings, Member, AuditLog
    assert mock_session.flush.call_count == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_workspace_slug_collision(service, mock_session, mock_workspace_repo):
    owner_id = uuid.uuid4()

    # Force collision once
    mock_workspace_repo.exists_by_slug.side_effect = [True, False]

    workspace = await service.provision_workspace(
        session=mock_session,
        name="Collision Corp",
        description=None,
        owner_user_id=owner_id
    )

    assert workspace.slug.startswith("collision-corp-")
    assert len(workspace.slug) > len("collision-corp-")
