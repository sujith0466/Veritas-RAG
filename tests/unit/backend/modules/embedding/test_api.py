"""Unit tests for Phase 2 Milestone 2: Embedding Pipeline (Milestone F - API Layer).

Verifies REST API route handlers, dependency overrides, DTO validation, status code mappings
(`202 Accepted` for jobs, `429 Too Many Requests` for `EMB_003`), and pagination formatting.
"""

from unittest.mock import AsyncMock, patch
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.main import create_app
from backend.modules.embedding.api.dependencies import get_embedding_service, resolve_tenant
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.schemas.errors import ProviderRateLimitError


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(app: FastAPI, mock_embedding_service: AsyncMock) -> TestClient:
    app.dependency_overrides[get_embedding_service] = lambda: mock_embedding_service
    app.dependency_overrides[resolve_tenant] = lambda: "test_tenant"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestEmbeddingAPI:
    """Test suite verifying `/api/v1/embeddings` endpoints and domain error status mapping."""

    @patch("backend.modules.embedding.api.routes.process_embedding_batch_task")
    def test_create_job_success(self, mock_celery_task: AsyncMock, client: TestClient, mock_embedding_service: AsyncMock) -> None:
        job_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        mock_job = EmbeddingJob(
            id=job_id,
            tenant_id="test_tenant",
            document_id=doc_id,
            document_version_id=ver_id,
            provider="openai",
            model_name="text-embedding-3-large",
            total_chunks=15,
            processed_chunks=0,
            status="PENDING",
        )
        mock_embedding_service.initiate_embedding_job.return_value = mock_job

        payload = {
            "document_id": str(doc_id),
            "document_version_id": str(ver_id),
            "provider": "openai",
            "batch_size": 100,
        }
        response = client.post("/api/v1/embeddings/jobs", json=payload)

        assert response.status_code == 202
        data = response.json()["data"]
        assert data["job_id"] == str(job_id)
        assert data["status"] == "PENDING"
        assert data["total_chunks"] == 15
        mock_celery_task.delay.assert_called_once_with(str(job_id), "test_tenant", 100, False)

    def test_create_job_rate_limit_maps_to_429(self, client: TestClient, mock_embedding_service: AsyncMock) -> None:
        mock_embedding_service.initiate_embedding_job.side_effect = ProviderRateLimitError(
            "OpenAI rate limit exceeded", detail={"retry_after": 60}
        )

        payload = {
            "document_id": str(uuid.uuid4()),
            "document_version_id": str(uuid.uuid4()),
        }
        response = client.post("/api/v1/embeddings/jobs", json=payload)

        assert response.status_code == 429
        error = response.json()["error"]
        assert error["code"] == "EMB_003"
        assert "rate limit exceeded" in error["message"]

    def test_get_job_success_and_404(self, client: TestClient, mock_embedding_service: AsyncMock) -> None:
        job_id = uuid.uuid4()
        mock_job = EmbeddingJob(
            id=job_id,
            tenant_id="test_tenant",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            provider="local",
            model_name="m",
            total_chunks=10,
            processed_chunks=5,
            status="PROCESSING",
        )
        mock_embedding_service.get_job_status.return_value = mock_job

        res_found = client.get(f"/api/v1/embeddings/jobs/{job_id}")
        assert res_found.status_code == 200
        assert res_found.json()["data"]["job_id"] == str(job_id)
        assert res_found.json()["data"]["processed_chunks"] == 5

        mock_embedding_service.get_job_status.return_value = None
        res_missing = client.get(f"/api/v1/embeddings/jobs/{uuid.uuid4()}")
        assert res_missing.status_code == 404

    def test_list_jobs_paginated(self, client: TestClient, mock_embedding_service: AsyncMock) -> None:
        mock_job = EmbeddingJob(
            id=uuid.uuid4(),
            tenant_id="test_tenant",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            provider="local",
            model_name="m",
            total_chunks=5,
            processed_chunks=5,
            status="COMPLETED",
        )
        mock_embedding_service.list_jobs.return_value = ([mock_job], 1)

        response = client.get("/api/v1/embeddings/jobs?page=1&size=10")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "COMPLETED"

    def test_get_metrics(self, client: TestClient, mock_embedding_service: AsyncMock) -> None:
        mock_embedding_service.get_tenant_metrics.return_value = {
            "tenant_id": "test_tenant",
            "monthly_token_quota": 1000000,
            "total_tokens_consumed": 15000,
            "remaining_tokens": 985000,
            "total_vectors_stored": 250,
            "active_jobs_count": 1,
            "completed_jobs_count": 4,
            "failed_jobs_count": 0,
            "provider_distribution": {"openai": 200, "cohere": 50},
        }

        response = client.get("/api/v1/embeddings/metrics")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_tokens_consumed"] == 15000
        assert data["provider_distribution"]["openai"] == 200

    def test_list_providers(self, client: TestClient) -> None:
        response = client.get("/api/v1/embeddings/providers")
        assert response.status_code == 200
        providers = response.json()["data"]
        assert len(providers) >= 3
        codes = {p["provider"] for p in providers}
        assert {"openai", "cohere", "local"}.issubset(codes)
