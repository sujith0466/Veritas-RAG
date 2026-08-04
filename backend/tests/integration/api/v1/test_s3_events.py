"""Integration tests for S3 direct uploads and webhook endpoints (F6.8)."""

from unittest.mock import AsyncMock, patch
import uuid

from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.permissions.rbac import Role
from backend.main import create_app

app = create_app()


def get_mock_member_user():
    return UserContext(
        id=uuid.uuid4(),
        email="user@example.com",
        role=Role.MEMBER,
        is_active=True,
        is_verified=True,
        supabase_id="mock-user-id",
    )


async def override_get_db():
    yield AsyncMock()


def test_generate_presigned_upload_endpoint():
    workspace_id = uuid.uuid4()
    mock_res = {
        "document_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "upload_url": "https://raguard-docs.s3.amazonaws.com/upload?sig=xyz",
        "object_key": "documents/ws1/doc1/v1/original/sample.pdf",
        "expires_in_seconds": 3600,
        "required_headers": {"Content-Type": "application/pdf"},
    }

    with patch("backend.document.api.v1.storage_webhooks._get_s3_event_service") as mock_get_service:
        mock_svc = AsyncMock()
        mock_svc.generate_presigned_upload.return_value = mock_res
        mock_get_service.return_value = mock_svc

        app.dependency_overrides[get_current_user] = get_mock_member_user
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/documents/presigned-upload",
            json={
                "filename": "sample.pdf",
                "file_size_bytes": 2048,
                "mime_type": "application/pdf",
            },
        )
        app.dependency_overrides.clear()

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["upload_url"].startswith("https://raguard-docs.s3.amazonaws.com")
        assert data["data"]["expires_in_seconds"] == 3600


def test_handle_s3_webhook_endpoint():
    payload = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "raguard-docs"},
                    "object": {
                        "key": "documents/tenant1/11111111-1111-1111-1111-111111111111/v1/original/report.pdf",
                        "eTag": "etag123",
                        "size": 4096,
                    },
                }
            }
        ]
    }

    with patch("backend.document.api.v1.storage_webhooks._get_s3_event_service") as mock_get_service:
        mock_svc = AsyncMock()
        mock_svc.handle_s3_object_created.return_value = {
            "status": "triggered",
            "document_id": "11111111-1111-1111-1111-111111111111",
            "job_id": str(uuid.uuid4()),
        }
        mock_get_service.return_value = mock_svc

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.post("/api/v1/webhooks/s3-events", json=payload)
        app.dependency_overrides.clear()

        assert response.status_code == 200
        res = response.json()
        assert res["status"] == "processed"
        assert len(res["results"]) == 1
        assert res["results"][0]["status"] == "triggered"
