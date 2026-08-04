"""Integration tests for Job DLQ endpoints (F6.6, F6.7)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.permissions.rbac import Role
from backend.document.models.job import ProcessingJob
import backend.document.workers.ingestion  # noqa: F401
from backend.main import create_app

app = create_app()


def get_mock_admin_user():
    return UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
        supabase_id="mock-admin-id",
    )


async def override_get_db():
    yield AsyncMock()


def test_list_dlq_jobs_endpoint():
    workspace_id = uuid.uuid4()
    mock_job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        status="DLQ",
        current_step="extraction",
        error_code="PARSE_ERR",
        error_message="Bad format",
        dlq_reason="[extraction] PARSE_ERR: Bad format",
        priority=1,
        retry_count=0,
        max_retries=3,
        dlq_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch("backend.document.repositories.job_repository.JobRepository.list_dlq_jobs", AsyncMock(return_value=[mock_job])):
        app.dependency_overrides[get_current_user] = get_mock_admin_user
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.get(f"/api/v1/workspaces/{workspace_id}/jobs/dlq")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["status"] == "DLQ"
        assert jobs[0]["error_code"] == "PARSE_ERR"


def test_retry_dlq_job_endpoint():
    workspace_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_job = ProcessingJob(
        id=job_id,
        document_id=uuid.uuid4(),
        status="DLQ",
        current_step="ocr",
        error_code="OCR_FAIL",
        error_message="Tesseract failure",
        dlq_reason="[ocr] OCR_FAIL: Tesseract failure",
        priority=1,
        retry_count=0,
        max_retries=3,
    )

    with patch("backend.document.repositories.job_repository.JobRepository.get_by_id", AsyncMock(return_value=mock_job)), \
         patch("backend.document.repositories.job_repository.JobRepository.reset_job_for_retry", AsyncMock(return_value=mock_job)), \
         patch("backend.document.repositories.failed_job_repository.FailedJobRepository.update_remediation_status", AsyncMock()), \
         patch("backend.document.repositories.job_audit_repository.JobAuditRepository.append", AsyncMock()), \
         patch("backend.document.workers.ingestion.process_document_job.apply_async", MagicMock()):

        app.dependency_overrides[get_current_user] = get_mock_admin_user
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/jobs/{job_id}/retry",
            json={"resume_from_step": "ocr"},
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["message"] == "Job successfully queued for retry"


def test_bulk_dismiss_dlq_jobs_endpoint():
    workspace_id = uuid.uuid4()
    job_id1 = uuid.uuid4()
    job_id2 = uuid.uuid4()

    with patch("backend.document.repositories.failed_job_repository.FailedJobRepository.bulk_dismiss", AsyncMock(return_value=2)):
        app.dependency_overrides[get_current_user] = get_mock_admin_user
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/jobs/dlq/bulk-dismiss",
            json={"job_ids": [str(job_id1), str(job_id2)]},
        )
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["count"] == 2
