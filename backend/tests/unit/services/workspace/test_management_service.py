from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import WorkspaceMember
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceManagementService,
    WorkspaceUnauthorizedError,
)


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()

@pytest.fixture
def mock_workspace_member_repo():
    return AsyncMock()

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def service(mock_workspace_repo, mock_workspace_member_repo):
    return WorkspaceManagementService(mock_workspace_repo, mock_workspace_member_repo)


@pytest.mark.asyncio
async def test_update_workspace_success(service, mock_session, mock_workspace_repo, mock_workspace_member_repo):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="OWNER")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    mock_workspace = Workspace(
        id=workspace_id,
        name="Old Name",
        description="Old Desc",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    workspace = await service.update_workspace(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=user_id,
        expected_updated_at=updated_at,
        name="New Name",
        description="New Desc"
    )

    assert workspace.name == "New Name"
    assert workspace.description == "New Desc"
    assert mock_session.add.call_count == 2  # Workspace, AuditLog


@pytest.mark.asyncio
async def test_update_workspace_conflict(service, mock_session, mock_workspace_repo, mock_workspace_member_repo):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # DB has a newer updated_at
    db_updated_at = datetime.now(UTC)
    expected_updated_at = db_updated_at - timedelta(minutes=5)

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="ADMIN")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    mock_workspace = Workspace(
        id=workspace_id,
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = db_updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(WorkspaceConflictError):
        await service.update_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=expected_updated_at,
            name="New Name"
        )


@pytest.mark.asyncio
async def test_update_workspace_unauthorized(service, mock_session, mock_workspace_member_repo):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # MEMBER role
    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="MEMBER")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    with pytest.raises(WorkspaceUnauthorizedError):
        await service.update_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=datetime.now(UTC),
            name="New Name"
        )


@pytest.mark.asyncio
async def test_update_workspace_skip_noop(service, mock_session, mock_workspace_repo, mock_workspace_member_repo):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="OWNER")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    mock_workspace = Workspace(
        id=workspace_id,
        name="Same Name",
        description="Same Desc",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    workspace = await service.update_workspace(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=user_id,
        expected_updated_at=updated_at,
        name="Same Name",
        description="Same Desc"
    )

    assert workspace.name == "Same Name"
    # Session add should not be called since no changes were made
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_archive_workspace_success(service, mock_session, mock_workspace_repo, mock_workspace_member_repo, monkeypatch):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="OWNER")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    mock_workspace = Workspace(
        id=workspace_id,
        name="Test Workspace",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    # Mock the dispatcher
    mock_dispatcher = AsyncMock()
    monkeypatch.setattr("backend.core.events.dispatcher.get_dispatcher", lambda: mock_dispatcher)

    workspace = await service.archive_workspace(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=user_id,
        expected_updated_at=updated_at,
        confirmation_name="Test Workspace",
        reason="Testing archive"
    )

    assert workspace.status == WorkspaceStatus.ARCHIVED.value
    assert mock_session.add.call_count == 2  # Workspace, AuditLog
    mock_dispatcher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_archive_workspace_confirmation_mismatch(service, mock_session, mock_workspace_repo, mock_workspace_member_repo):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="OWNER")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    mock_workspace = Workspace(
        id=workspace_id,
        name="Test Workspace",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(ValueError):
        await service.archive_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=updated_at,
            confirmation_name="Wrong Name"
        )


@pytest.mark.asyncio
async def test_restore_workspace_success(service, mock_session, mock_workspace_repo, mock_workspace_member_repo, monkeypatch):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="OWNER")
    mock_workspace_member_repo.get_membership.return_value = mock_member

    mock_workspace = Workspace(
        id=workspace_id,
        name="Test Workspace",
        status=WorkspaceStatus.ARCHIVED.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    # Mock the dispatcher
    mock_dispatcher = AsyncMock()
    monkeypatch.setattr("backend.core.events.dispatcher.get_dispatcher", lambda: mock_dispatcher)

    workspace = await service.restore_workspace(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=user_id,
        expected_updated_at=updated_at
    )

    assert workspace.status == WorkspaceStatus.ACTIVE.value
    assert mock_session.add.call_count == 2
    mock_dispatcher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_suspend_workspace_success(service, mock_session, mock_workspace_repo, monkeypatch):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_dispatcher = AsyncMock()
    monkeypatch.setattr("backend.core.events.dispatcher.get_dispatcher", lambda: mock_dispatcher)

    workspace = await service.suspend_workspace(
        session=mock_session,
        workspace_id=workspace_id,
        admin_id=admin_id,
        admin_email="admin@raguard.ai",
        expected_updated_at=updated_at,
        confirmation_name="Production Workspace",
        reason_code="BILLING",
        reason_text="Payment overdue"
    )

    assert workspace.status == WorkspaceStatus.SUSPENDED.value
    assert workspace.suspended_at is not None
    assert mock_session.add.call_count == 2  # Workspace, AuditLog
    mock_dispatcher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_suspend_workspace_confirmation_mismatch(service, mock_session, mock_workspace_repo):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(ValueError):
        await service.suspend_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            admin_id=admin_id,
            admin_email="admin@raguard.ai",
            expected_updated_at=updated_at,
            confirmation_name="Wrong Workspace",
            reason_code="BILLING",
            reason_text="Payment overdue"
        )


@pytest.mark.asyncio
async def test_suspend_workspace_already_suspended_conflict(service, mock_session, mock_workspace_repo):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.SUSPENDED.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(WorkspaceConflictError, match="already suspended"):
        await service.suspend_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            admin_id=admin_id,
            admin_email="admin@raguard.ai",
            expected_updated_at=updated_at,
            confirmation_name="Production Workspace",
            reason_code="BILLING",
            reason_text="Payment overdue"
        )


@pytest.mark.asyncio
async def test_suspend_workspace_concurrency_conflict(service, mock_session, mock_workspace_repo):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    db_updated_at = datetime.now(UTC)
    expected_updated_at = db_updated_at - timedelta(minutes=5)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = db_updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(WorkspaceConflictError, match="modified by another administrator"):
        await service.suspend_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            admin_id=admin_id,
            admin_email="admin@raguard.ai",
            expected_updated_at=expected_updated_at,
            confirmation_name="Production Workspace",
            reason_code="BILLING",
            reason_text="Payment overdue"
        )


@pytest.mark.asyncio
async def test_unsuspend_workspace_success(service, mock_session, mock_workspace_repo, monkeypatch):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.SUSPENDED.value,
        suspended_at=datetime.now(UTC)
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_dispatcher = AsyncMock()
    monkeypatch.setattr("backend.core.events.dispatcher.get_dispatcher", lambda: mock_dispatcher)

    workspace = await service.unsuspend_workspace(
        session=mock_session,
        workspace_id=workspace_id,
        admin_id=admin_id,
        admin_email="admin@raguard.ai",
        expected_updated_at=updated_at,
        reason_text="Payment resolved"
    )

    assert workspace.status == WorkspaceStatus.ACTIVE.value
    assert workspace.suspended_at is None
    assert mock_session.add.call_count == 2
    mock_dispatcher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_unsuspend_workspace_already_active_conflict(service, mock_session, mock_workspace_repo):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    updated_at = datetime.now(UTC)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace.updated_at = updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(WorkspaceConflictError, match="not suspended"):
        await service.unsuspend_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            admin_id=admin_id,
            admin_email="admin@raguard.ai",
            expected_updated_at=updated_at,
            reason_text="Payment resolved"
        )


@pytest.mark.asyncio
async def test_unsuspend_workspace_concurrency_conflict(service, mock_session, mock_workspace_repo):
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    db_updated_at = datetime.now(UTC)
    expected_updated_at = db_updated_at - timedelta(minutes=5)

    mock_workspace = Workspace(
        id=workspace_id,
        name="Production Workspace",
        status=WorkspaceStatus.SUSPENDED.value,
    )
    mock_workspace.updated_at = db_updated_at
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(WorkspaceConflictError, match="modified by another administrator"):
        await service.unsuspend_workspace(
            session=mock_session,
            workspace_id=workspace_id,
            admin_id=admin_id,
            admin_email="admin@raguard.ai",
            expected_updated_at=expected_updated_at,
            reason_text="Payment resolved"
        )

