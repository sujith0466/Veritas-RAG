"""Unit tests for S3EventService (F6.8)."""

from unittest.mock import AsyncMock
import uuid

import pytest

from backend.document.models.document import Document
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.services.s3_event_service import S3EventService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_storage():
    mock = AsyncMock()
    mock.provider_name = "s3"
    mock.bucket_name = "test-bucket"
    mock.create_upload_url.return_value = "https://test-bucket.s3.amazonaws.com/upload?sig=123"
    return mock


@pytest.fixture
def mock_doc_repo():
    return AsyncMock()


@pytest.fixture
def mock_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_job_service():
    return AsyncMock()


@pytest.fixture
def mock_event_repo():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.set.return_value = True  # New event
    return mock


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def s3_service(
    mock_storage,
    mock_doc_repo,
    mock_job_repo,
    mock_job_service,
    mock_event_repo,
    mock_redis,
):
    return S3EventService(
        storage_provider=mock_storage,
        document_repo=mock_doc_repo,
        job_repo=mock_job_repo,
        job_service=mock_job_service,
        event_repo=mock_event_repo,
        redis_client=mock_redis,
    )


async def test_generate_presigned_upload(s3_service, mock_storage, mock_session):
    res = await s3_service.generate_presigned_upload(
        tenant_id="test-tenant",
        filename="financial_report.pdf",
        file_size_bytes=10240,
        mime_type="application/pdf",
        checksum_sha256="abc123sha",
        folder_id=None,
        user_id=uuid.uuid4(),
        session=mock_session,
    )

    assert "upload_url" in res
    assert res["upload_url"].startswith("https://test-bucket.s3.amazonaws.com/upload")
    assert "document_id" in res
    assert "version_id" in res
    assert res["expires_in_seconds"] == 3600
    assert res["required_headers"] == {"Content-Type": "application/pdf"}
    mock_session.flush.assert_called()


async def test_handle_s3_object_created_idempotent(
    s3_service, mock_redis, mock_doc_repo, mock_job_service, mock_session
):
    doc_id = uuid.uuid4()
    object_key = f"documents/test-tenant/{doc_id}/v1/original/financial_report.pdf"

    mock_doc = Document(id=doc_id, tenant_id="test-tenant", status=DocumentStatus.PENDING)
    mock_doc_repo.get_by_id.return_value = mock_doc

    mock_job = ProcessingJob(id=uuid.uuid4(), document_id=doc_id, status="QUEUED")
    mock_job_service.enqueue_job.return_value = mock_job

    # 1. First event succeeds and enqueues job
    res1 = await s3_service.handle_s3_object_created(
        bucket="test-bucket",
        object_key=object_key,
        etag="etag-12345",
        size_bytes=10240,
        session=mock_session,
    )
    assert res1["status"] == "triggered"
    assert res1["document_id"] == str(doc_id)
    assert mock_doc.status == DocumentStatus.UPLOADED

    # 2. Duplicate event ignored
    mock_redis.set.return_value = False
    res2 = await s3_service.handle_s3_object_created(
        bucket="test-bucket",
        object_key=object_key,
        etag="etag-12345",
        size_bytes=10240,
        session=mock_session,
    )
    assert res2["status"] == "duplicate_ignored"
