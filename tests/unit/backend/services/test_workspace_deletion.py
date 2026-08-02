"""Unit tests for F3.5 Workspace Soft Delete, Restore, and Hard Delete."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceInvalidStateError,
    WorkspaceManagementService,
    WorkspaceUnauthorizedError,
)
from backend.services.workspace.retention_worker import WorkspaceRetentionWorker


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def workspace_repo(mock_session):
    repo = AsyncMock(spec=WorkspaceRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def member_repo(mock_session):
    repo = AsyncMock(spec=WorkspaceMemberRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def service(workspace_repo, member_repo):
    return WorkspaceManagementService(workspace_repo, member_repo)


@pytest.mark.asyncio
async def test_soft_delete_workspace_owner_success(service, workspace_repo, member_repo, mock_session):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.ACTIVE.value,
        updated_at=now,
        storage_prefix="acme",
        qdrant_namespace="acme",
    )
    workspace_repo.get_by_id.return_value = ws
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        deleted_ws = await service.soft_delete_workspace(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            confirmation_name="Acme Corp",
            reason_code="USER_REQUESTED",
            reason_text="Closing department",
            is_platform_admin=False,
        )

    assert deleted_ws.status == WorkspaceStatus.DELETING.value
    assert deleted_ws.deleted_at is not None
    assert deleted_ws.purge_at is not None
    assert deleted_ws.deleted_by_user_id == user_id
    assert deleted_ws.deletion_reason_code == "USER_REQUESTED"
    assert deleted_ws.deletion_reason_text == "Closing department"


@pytest.mark.asyncio
async def test_soft_delete_workspace_admin_forbidden(service, workspace_repo, member_repo, mock_session):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.ACTIVE.value,
        updated_at=now,
        storage_prefix="acme",
        qdrant_namespace="acme",
    )
    workspace_repo.get_by_id.return_value = ws
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError):
        await service.soft_delete_workspace(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            confirmation_name="Acme Corp",
            reason_code="USER_REQUESTED",
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_soft_delete_name_mismatch(service, workspace_repo, member_repo, mock_session):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.ACTIVE.value,
        updated_at=now,
        storage_prefix="acme",
        qdrant_namespace="acme",
    )
    workspace_repo.get_by_id.return_value = ws
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )

    with pytest.raises(ValueError, match="Confirmation name does not match"):
        await service.soft_delete_workspace(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            confirmation_name="Wrong Corp",
            reason_code="USER_REQUESTED",
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_soft_delete_concurrency_conflict(service, workspace_repo, member_repo, mock_session):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    stale_time = now - timedelta(minutes=5)
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.ACTIVE.value,
        updated_at=now,
        storage_prefix="acme",
        qdrant_namespace="acme",
    )
    workspace_repo.get_by_id.return_value = ws
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )

    with pytest.raises(WorkspaceConflictError):
        await service.soft_delete_workspace(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=stale_time,
            confirmation_name="Acme Corp",
            reason_code="USER_REQUESTED",
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_restore_deleted_workspace_success(service, workspace_repo, member_repo, mock_session):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    future_purge = now + timedelta(days=25)
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.DELETING.value,
        updated_at=now,
        deleted_at=now - timedelta(days=5),
        purge_at=future_purge,
        deleted_by_user_id=user_id,
        deletion_reason_code="USER_REQUESTED",
        storage_prefix="acme",
        qdrant_namespace="acme",
    )
    workspace_repo.get_by_id.return_value = ws
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        restored_ws = await service.restore_deleted_workspace(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            is_platform_admin=False,
        )

    assert restored_ws.status == WorkspaceStatus.ACTIVE.value
    assert restored_ws.deleted_at is None
    assert restored_ws.purge_at is None
    assert restored_ws.deleted_by_user_id is None
    assert restored_ws.deletion_reason_code is None


@pytest.mark.asyncio
async def test_restore_deleted_workspace_expired_window(service, workspace_repo, member_repo, mock_session):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    past_purge = now - timedelta(days=1)
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.DELETING.value,
        updated_at=now,
        deleted_at=now - timedelta(days=31),
        purge_at=past_purge,
        storage_prefix="acme",
        qdrant_namespace="acme",
    )
    workspace_repo.get_by_id.return_value = ws
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )

    with pytest.raises(WorkspaceInvalidStateError, match="retention window.*expired"):
        await service.restore_deleted_workspace(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_hard_delete_workspace_success(service, workspace_repo, mock_session):
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        status=WorkspaceStatus.DELETING.value,
        storage_prefix="acme-prefix",
        qdrant_namespace="acme-namespace",
    )
    workspace_repo.get_by_id.return_value = ws
    workspace_repo.delete.return_value = True

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        res = await service.hard_delete_workspace(
            session=mock_session,
            workspace_id=ws_id,
            admin_id=admin_id,
            confirmation_slug="acme-corp",
            reason="Legal compliance cleanup",
            force_immediate=False,
        )

    assert res["status"] == "PURGED"
    assert res["workspace_id"] == str(ws_id)
    workspace_repo.delete.assert_awaited_once_with(ws_id)


@pytest.mark.asyncio
async def test_retention_worker_run(service, mock_session):
    worker = WorkspaceRetentionWorker(service)
    ws_id = uuid.uuid4()
    now = datetime.now(UTC)
    ws = Workspace(
        id=ws_id,
        name="Expired Corp",
        slug="expired-corp",
        status=WorkspaceStatus.DELETING.value,
        purge_at=now - timedelta(hours=1),
        storage_prefix="exp",
        qdrant_namespace="exp",
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ws]
    mock_session.execute.return_value = mock_result

    service.hard_delete_workspace = AsyncMock(return_value={"status": "PURGED"})

    metrics = await worker.run_retention_cleanup(mock_session)
    assert metrics["processed"] == 1
    assert metrics["purged"] == 1
    assert metrics["failed"] == 0
