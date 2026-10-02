"""Unit tests for hardened DocumentService dispatching (Phase D2.2)."""

import io
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.job import DispatchState, ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.services.document_service import DocumentService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def service():
    with patch("backend.document.services.document_service.DocumentRepository") as repo_cls, \
         patch("backend.document.services.document_service.JobRepository") as job_repo_cls, \
         patch("backend.document.services.document_service.StorageObjectRepository") as storage_repo_cls, \
         patch("backend.document.services.document_service.LocalStorageProvider") as storage_cls, \
         patch("backend.document.services.document_service.DocumentEventRepository") as event_repo_cls, \
         patch("backend.document.services.document_service.ValidationPipeline") as val_cls:

        repo_cls.return_value = AsyncMock()
        job_repo_cls.return_value = AsyncMock()
        storage_repo_cls.return_value = AsyncMock()
        storage_cls.return_value = AsyncMock()
        event_repo_cls.return_value = AsyncMock()
        val_cls.return_value = AsyncMock()
        return DocumentService()


@pytest.mark.asyncio
async def test_upload_document_dispatch_success(service, mock_session):
    """Test upload_document dispatches job and marks DISPATCHED with task ID."""
    stream = io.BytesIO(b"sample file content")
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    version_id = uuid.uuid4()

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.status = DocumentStatus.UPLOADED

    mock_job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        version_id=version_id,
        status="PENDING",
        current_step="upload",
        dispatch_state=DispatchState.PENDING_DISPATCH.value,
    )

    # Mock validation result
    val_mock = MagicMock()
    val_mock.content_hash = "sha256hash"
    val_mock.sanitized_filename = "test.txt"
    val_mock.detected_mime = "text/plain"
    service.validator.validate = AsyncMock(return_value=val_mock)

    # Mock storage
    storage_dto = MagicMock()
    storage_dto.file_size_bytes = 19
    storage_dto.storage_provider = "local"
    storage_dto.bucket_or_container = "/app/data/storage"
    storage_dto.object_key = "test/key/test.txt"
    service.storage.save_stream = AsyncMock(return_value=storage_dto)

    service.doc_repo.create = AsyncMock(return_value=mock_doc)
    service.doc_repo.add_version = AsyncMock(return_value=MagicMock(id=version_id))
    service.job_repo.create = AsyncMock(return_value=mock_job)

    mock_task = MagicMock()
    mock_task.id = "task-upload-success"

    with patch("backend.document.services.document_service.check_duplicate_content", return_value=None), \
         patch("backend.document.workers.ingestion.process_document_job.apply_async", return_value=mock_task):

        doc, version, job = await service.upload_document(
            stream=stream,
            filename="test.txt",
            declared_mime="text/plain",
            tenant_id="tenant-123",
            owner_user_id=uuid.uuid4(),
            session=mock_session,
        )

        assert job.dispatch_state == DispatchState.DISPATCHED.value
        assert job.celery_task_id == "task-upload-success"
        assert job.dispatch_error is None
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_upload_document_dispatch_failure_records_error(service, mock_session):
    """Test upload_document records FAILED_DISPATCH on broker failure without losing document."""
    stream = io.BytesIO(b"sample file content")
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()
    version_id = uuid.uuid4()

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.status = DocumentStatus.UPLOADED

    mock_job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        version_id=version_id,
        status="PENDING",
        current_step="upload",
        dispatch_state=DispatchState.PENDING_DISPATCH.value,
    )

    val_mock = MagicMock()
    val_mock.content_hash = "sha256hash"
    val_mock.sanitized_filename = "test.txt"
    val_mock.detected_mime = "text/plain"
    service.validator.validate = AsyncMock(return_value=val_mock)

    storage_dto = MagicMock()
    storage_dto.file_size_bytes = 19
    storage_dto.storage_provider = "local"
    storage_dto.bucket_or_container = "/app/data/storage"
    storage_dto.object_key = "test/key/test.txt"
    service.storage.save_stream = AsyncMock(return_value=storage_dto)

    service.doc_repo.create = AsyncMock(return_value=mock_doc)
    service.doc_repo.add_version = AsyncMock(return_value=MagicMock(id=version_id))
    service.job_repo.create = AsyncMock(return_value=mock_job)

    with patch("backend.document.services.document_service.check_duplicate_content", return_value=None), \
         patch("backend.document.workers.ingestion.process_document_job.apply_async", side_effect=ConnectionRefusedError("Redis down")):

        doc, version, job = await service.upload_document(
            stream=stream,
            filename="test.txt",
            declared_mime="text/plain",
            tenant_id="tenant-123",
            owner_user_id=uuid.uuid4(),
            session=mock_session,
        )

        assert job.dispatch_state == DispatchState.FAILED_DISPATCH.value
        assert "Redis down" in job.dispatch_error
        assert doc.status == DocumentStatus.UPLOADED
        mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_upload_new_version_dispatch_failure_records_error(service, mock_session):
    """Test upload_new_version records FAILED_DISPATCH when broker unreachable."""
    stream = io.BytesIO(b"v2 content")
    doc_id = uuid.uuid4()
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.versions = [MagicMock(version_number=1)]

    service.doc_repo.get_by_id_with_versions = AsyncMock(return_value=mock_doc)

    val_mock = MagicMock()
    val_mock.content_hash = "sha256v2"
    val_mock.sanitized_filename = "v2.txt"
    val_mock.detected_mime = "text/plain"
    service.validator.validate = AsyncMock(return_value=val_mock)

    storage_dto = MagicMock()
    storage_dto.file_size_bytes = 10
    storage_dto.storage_provider = "local"
    storage_dto.bucket_or_container = "/app/data/storage"
    storage_dto.object_key = "test/key/v2.txt"
    service.storage.save_stream = AsyncMock(return_value=storage_dto)

    version_mock = MagicMock()
    version_mock.id = uuid.uuid4()
    service.doc_repo.add_version = AsyncMock(return_value=version_mock)

    mock_job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_id=version_mock.id,
        status="PENDING",
        current_step="upload",
        dispatch_state=DispatchState.PENDING_DISPATCH.value,
    )
    service.job_repo.create = AsyncMock(return_value=mock_job)

    with patch("backend.document.workers.ingestion.process_document_job.apply_async", side_effect=TimeoutError("Celery timeout")):

        doc, version, job = await service.upload_new_version(
            document_id=doc_id,
            stream=stream,
            filename="v2.txt",
            declared_mime="text/plain",
            tenant_id="tenant-123",
            owner_user_id=uuid.uuid4(),
            session=mock_session,
        )

        assert job.dispatch_state == DispatchState.FAILED_DISPATCH.value
        assert "Celery timeout" in job.dispatch_error
        assert doc.status == DocumentStatus.UPLOADED
        mock_session.commit.assert_called()
