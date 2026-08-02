import pytest
import uuid
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user

app = create_app()

def get_mock_verified_user():
    return UserContext(
        id=uuid.uuid4(),
        email="test@example.com",
        role="user",
        is_active=True,
        is_verified=True,
        supabase_id=None,
        session_id=uuid.uuid4()
    )

def get_mock_unverified_user():
    return UserContext(
        id=uuid.uuid4(),
        email="unverified@example.com",
        role="user",
        is_active=True,
        is_verified=False,
        supabase_id=None,
        session_id=uuid.uuid4()
    )


def test_create_workspace_success():
    app.dependency_overrides[get_current_user] = get_mock_verified_user
    client = TestClient(app)

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Integration Corp", "description": "Testing create"}
    )
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Integration Corp"
    assert data["data"]["slug"] == "integration-corp"
    assert data["data"]["status"] == "ACTIVE"
    assert data["data"]["provisioning_status"] == "READY"


def test_create_workspace_unverified():
    app.dependency_overrides[get_current_user] = get_mock_unverified_user
    client = TestClient(app)

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Unverified Corp"}
    )
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 403
    assert "Email verification required" in response.json()["detail"]
