from unittest.mock import AsyncMock, MagicMock
import uuid
from datetime import datetime, UTC

from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_folder_service
from backend.core.permissions.rbac import Role
from backend.main import create_app
from backend.models.entities.folder import Folder
from backend.api.v1.schemas.folder import DeletionQueuedResponse, RestoreQueuedResponse

app = create_app()

def get_mock_admin_user():
    return UserContext(
        id=uuid.uuid4(),
        email="test@example.com",
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
        supabase_id="mock-supabase-id",
    )

def test_create_folder_api():
    mock_service = MagicMock()
    folder_id = uuid.uuid4()
    mock_folder = Folder(
        id=folder_id,
        workspace_id=uuid.uuid4(),
        name="API Folder",
        slug="api-folder",
        depth=0,
        path=str(folder_id),
        version=1,
        document_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        is_deleted=False,
    )
    mock_service.create_folder = AsyncMock(return_value=mock_folder)

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_folder_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"/api/v1/workspaces/{uuid.uuid4()}/folders",
        json={"name": "API Folder"}
    )
    
    assert response.status_code == 201
    assert response.json()["name"] == "API Folder"
    
    app.dependency_overrides.clear()

def test_rename_folder_api():
    mock_service = MagicMock()
    folder_id = uuid.uuid4()
    mock_folder = Folder(
        id=folder_id,
        workspace_id=uuid.uuid4(),
        name="Renamed API",
        slug="renamed-api",
        depth=0,
        path=str(folder_id),
        version=2,
        document_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        is_deleted=False,
    )
    mock_service.rename_folder = AsyncMock(return_value=mock_folder)

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_folder_service] = lambda: mock_service

    client = TestClient(app)
    response = client.patch(
        f"/api/v1/workspaces/{uuid.uuid4()}/folders/{folder_id}",
        json={"name": "Renamed API", "version": 1}
    )
    
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed API"
    
    app.dependency_overrides.clear()

def test_soft_delete_folder_api():
    mock_service = MagicMock()
    mock_service.soft_delete_folder = AsyncMock(return_value="task-123")

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_folder_service] = lambda: mock_service

    client = TestClient(app)
    response = client.delete(
        f"/api/v1/workspaces/{uuid.uuid4()}/folders/{uuid.uuid4()}?version=1"
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "deletion_queued"
    
    app.dependency_overrides.clear()


def test_move_folder_api():
    mock_service = MagicMock()
    mock_service.move_folder = AsyncMock(return_value={"status": "accepted", "worker_task_id": "task-123", "cascade_pending": True})

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_folder_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"/api/v1/workspaces/{uuid.uuid4()}/folders/{uuid.uuid4()}/move",
        json={"target_parent_id": str(uuid.uuid4()), "version": 1}
    )
    
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    app.dependency_overrides.clear()

def test_early_hard_delete_folder_api():
    mock_service = MagicMock()


def test_move_folder_api():
    mock_service = MagicMock()
    mock_service.move_folder = AsyncMock(return_value={"status": "accepted", "worker_task_id": "task-123", "cascade_pending": True})

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_folder_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"/api/v1/workspaces/{uuid.uuid4()}/folders/{uuid.uuid4()}/move",
        json={"target_parent_id": str(uuid.uuid4()), "version": 1}
    )
    
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    
    app.dependency_overrides.clear()

def test_early_hard_delete_folder_api():
    mock_service = MagicMock()
    mock_service.early_hard_delete_folder = AsyncMock(return_value={"status": "purge_scheduled", "purge_at": "immediate", "worker_task_id": "task-456"})

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_folder_service] = lambda: mock_service

    client = TestClient(app)
    response = client.request(
        "DELETE",
        f"/api/v1/workspaces/{uuid.uuid4()}/folders/{uuid.uuid4()}/hard-delete",
        json={"confirmation_name": "delete me"}
    )
    
    assert response.status_code == 202
    assert response.json()["status"] == "purge_scheduled"
    
    app.dependency_overrides.clear()
