"""Unit tests for Vector Storage REST API Layer (`ADR-M3-001`).

Verifies route handler response formatting, status codes (`202 Accepted` for sync job initiation,
`200 OK` for inspection/purge), dependency injection overrides, and Celery task dispatching.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.main import create_app
from backend.modules.vector.api.dependencies import (
    get_vector_repository,
    get_vector_service,
    resolve_tenant,
)
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def mock_vector_service() -> AsyncMock:
    service = AsyncMock()
    service.provider.check_connection.return_value = True
    return service


@pytest.fixture
def mock_vector_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(app: FastAPI, mock_vector_service: AsyncMock, mock_vector_repository: AsyncMock) -> TestClient:
    app.dependency_overrides[get_vector_service] = lambda: mock_vector_service
    app.dependency_overrides[get_vector_repository] = lambda: mock_vector_repository
    app.dependency_overrides[resolve_tenant] = lambda: "test_tenant"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestVectorAPI:
    """Test suite verifying `/api/v1/vectors/*` endpoints (`ADR-M3-001`)."""

    @patch("backend.modules.vector.api.routes.sync_vectors_to_qdrant_task")
    def test_sync_document_vectors_accepted(
        self, mock_celery_task: MagicMock, client: TestClient, mock_vector_repository: AsyncMock
    ) -> None:
        meta_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        mock_meta = VectorIndexMetadata(
            id=meta_id,
            tenant_id="test_tenant",
            document_id=doc_id,
            document_version_id=ver_id,
            collection_name="raguard_knowledge_1536",
            status="PENDING",
            points_count=0,
        )
        mock_vector_repository.get_or_create_metadata.return_value = mock_meta

        payload = {
            "document_id": str(doc_id),
            "collection_name": "raguard_knowledge_1536",
        }

        response = client.post(f"/api/v1/vectors/sync/{ver_id}", json=payload)
        assert response.status_code == 202
        data = response.json()["data"]
        assert data["id"] == str(meta_id)
        assert data["status"] == "PENDING"
        mock_celery_task.delay.assert_called_once_with(
            str(doc_id),
            str(ver_id),
            "test_tenant",
            "raguard_knowledge_1536",
        )

    @patch("backend.modules.vector.api.routes.select")
    def test_get_document_sync_status(
        self, mock_select: MagicMock, client: TestClient, app: FastAPI
    ) -> None:
        from backend.core.dependencies.database import get_db
        meta_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        mock_meta = VectorIndexMetadata(
            id=meta_id,
            tenant_id="test_tenant",
            document_id=doc_id,
            document_version_id=ver_id,
            collection_name="raguard_knowledge_1536",
            status="COMPLETED",
            points_count=45,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_meta]
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_db] = lambda: mock_session

        response = client.get(f"/api/v1/vectors/document/{doc_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(meta_id)
        assert data[0]["status"] == "COMPLETED"
        assert data[0]["points_count"] == 45

    def test_get_qdrant_health_online(self, client: TestClient, mock_vector_service: AsyncMock) -> None:
        mock_vector_service.get_tenant_summary.return_value = {
            "tenant_id": "test_tenant",
            "total_points_stored": 1250,
            "collections": [
                {
                    "collection_name": "raguard_knowledge_1536",
                    "total_points": 1250,
                    "indexed_versions_count": 8,
                }
            ],
        }

        response = client.get("/api/v1/vectors/health")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "ONLINE"
        assert data["active_collections_count"] == 1
        assert data["total_points_stored"] == 1250
        assert data["collections"][0]["collection_name"] == "raguard_knowledge_1536"

    def test_list_tenant_collections(self, client: TestClient, mock_vector_service: AsyncMock) -> None:
        mock_vector_service.get_tenant_summary.return_value = {
            "tenant_id": "test_tenant",
            "total_points_stored": 500,
            "collections": [
                {
                    "collection_name": "raguard_knowledge_1536",
                    "total_points": 500,
                    "indexed_versions_count": 3,
                }
            ],
        }

        response = client.get("/api/v1/vectors/collections")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["collection_name"] == "raguard_knowledge_1536"
        assert data[0]["total_points"] == 500

    def test_delete_document_points(self, client: TestClient, mock_vector_service: AsyncMock) -> None:
        doc_id = uuid.uuid4()
        mock_vector_service.delete_document_points.return_value = 15

        response = client.delete(f"/api/v1/vectors/document/{doc_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["document_id"] == str(doc_id)
        assert data["tenant_id"] == "test_tenant"
        assert data["purged_points_count"] == 15
