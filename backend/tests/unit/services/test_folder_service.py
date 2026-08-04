from unittest.mock import AsyncMock
import uuid

import pytest

from backend.models.entities.folder import Folder
from backend.services.folder_service import FolderConflictError, FolderService


@pytest.fixture
def service():
    session = AsyncMock()
    dispatcher = AsyncMock()
    svc = FolderService(session, dispatcher)
    svc.repo = AsyncMock()
    svc._check_rate_limits = AsyncMock() # Skip Redis in unit tests
    return svc

@pytest.mark.asyncio
async def test_create_folder_success(service):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    service.repo.count_folders.return_value = 0
    service.repo.exists_name_in_parent.return_value = False

    folder = await service.create_folder(workspace_id, actor_id, "Test Folder")

    assert folder.name == "Test Folder"
    assert folder.slug == "test-folder"
    assert folder.depth == 0
    service.session.add.assert_called()

@pytest.mark.asyncio
async def test_create_folder_conflict(service):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    service.repo.count_folders.return_value = 0
    service.repo.exists_name_in_parent.return_value = True

    with pytest.raises(FolderConflictError):
        await service.create_folder(workspace_id, actor_id, "Test Folder")

@pytest.mark.asyncio
async def test_rename_folder_success(service):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    folder_id = uuid.uuid4()

    existing = Folder(id=folder_id, workspace_id=workspace_id, name="Old", slug="old", version=1, parent_id=None)
    service.repo.get_by_id_in_workspace.return_value = existing
    service.repo.exists_name_in_parent.return_value = False
    service.repo.get_subtree_ids.return_value = [folder_id]

    from backend.services.folder_service import FolderCache
    FolderCache.invalidate_for_rename = AsyncMock()

    folder = await service.rename_folder(workspace_id, actor_id, folder_id, "New Name", 1)

    assert folder.name == "New Name"
    assert folder.slug == "new-name"
    assert folder.version == 2
    service.dispatcher.publish.assert_called_once()
