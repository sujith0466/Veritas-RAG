"""Unit tests for Document Retry and Re-ingest logic (D3.4)."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models import Document, DocumentVersion, StorageObject, ProcessingJob, DocumentStatus
from backend.document.models.job import DispatchState

from backend.document.schemas.errors import DocumentDomainException
from backend.document.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_retry_document_failed_success():
    """Test retrying a FAILED document resets state and dispatches job."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    storage_obj = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key="test-tenant/docs/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        checksum_sha256="dummy-checksum",

    )
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        storage_object=storage_obj,
    )
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="test.pdf",
        status=DocumentStatus.FAILED,
        latest_version_id=ver_id,
        versions=[version],
    )
    job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_id=ver_id,
        status="FAILED",
        current_step="ocr",
        retry_count=2,
    )

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc), \
         patch.object(service.job_repo, "get_by_document_id", return_value=job), \
         patch.object(service.event_repo, "append_event", return_value=None), \
         patch("backend.document.storage.preflight.StoragePreflightValidator.validate") as mock_val, \
         patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", return_value=MagicMock(success=True)) as mock_dispatch:

        mock_val.return_value = MagicMock(is_valid=True)

        res_doc, res_job = await service.retry_document(doc_id, "test-tenant", session)

        assert res_doc.status == DocumentStatus.UPLOADED
        assert res_job.status == DocumentStatus.PENDING
        assert res_job.current_step == "upload"
        assert res_job.retry_count == 0
        assert res_job.dispatch_state == DispatchState.PENDING_DISPATCH.value
        mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_retry_document_non_failed_rejected():
    """Test retrying a READY or PROCESSED document raises domain exception."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="test.pdf",
        status=DocumentStatus.READY,
        versions=[],
    )

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc):
        with pytest.raises(DocumentDomainException) as exc_info:
            await service.retry_document(doc_id, "test-tenant", session)
        assert "Only documents in FAILED status can be retried" in str(exc_info.value)


@pytest.mark.asyncio
async def test_retry_document_storage_missing_rejected():
    """Test retrying a FAILED document with missing storage fails preflight."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    storage_obj = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key="test-tenant/docs/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        checksum_sha256="dummy-checksum",

    )
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        storage_object=storage_obj,
    )
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="test.pdf",
        status=DocumentStatus.FAILED,
        latest_version_id=ver_id,
        versions=[version],
    )

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc), \
         patch("backend.document.storage.preflight.StoragePreflightValidator.validate") as mock_val:

        mock_val.return_value = MagicMock(is_valid=False, error_message="File not found on disk")

        with pytest.raises(DocumentDomainException) as exc_info:
            await service.retry_document(doc_id, "test-tenant", session)
        assert "Storage pre-flight check failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_reingest_document_ready_success():
    """Test re-ingesting a READY document purges chunks and dispatches new ingestion."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    storage_obj = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key="test-tenant/docs/test.pdf",
        file_size_bytes=1024,
        mime_type="application/pdf",
        checksum_sha256="dummy-checksum",

    )
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        storage_object=storage_obj,
    )
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="test.pdf",
        status=DocumentStatus.READY,
        latest_version_id=ver_id,
        versions=[version],
    )
    job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        version_id=ver_id,
        status="COMPLETED",
        current_step="completed",
        retry_count=0,
    )

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc), \
         patch.object(service.job_repo, "get_by_document_id", return_value=job), \
         patch.object(service.event_repo, "append_event", return_value=None), \
         patch("backend.document.storage.preflight.StoragePreflightValidator.validate") as mock_val, \
         patch("backend.modules.vector.services.vector_service.VectorStorageService.delete_document_points", return_value=10) as mock_vec_del, \
         patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", return_value=MagicMock(success=True)) as mock_dispatch:

        mock_val.return_value = MagicMock(is_valid=True)

        res_doc, res_job = await service.reingest_document(doc_id, "test-tenant", session)

        assert res_doc.status == DocumentStatus.UPLOADED
        assert res_job.status == DocumentStatus.PENDING
        assert res_job.current_step == "upload"
        mock_vec_del.assert_called_once_with(doc_id, "test-tenant")
        mock_dispatch.assert_called_once()
