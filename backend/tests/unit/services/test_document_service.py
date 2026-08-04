from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.status import DocumentStatus
from backend.document.services.document_service import DocumentService


class DummyAsyncContextManager:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

# Ensure workers module is loaded so patch can find it

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def mock_repo():
    return AsyncMock()

@pytest.fixture
def mock_job_repo():
    return AsyncMock()

@pytest.fixture
def mock_storage():
    return AsyncMock()

@pytest.fixture
def mock_event_repo():
    return AsyncMock()

@pytest.fixture
def service():
    with patch("backend.document.services.document_service.DocumentRepository") as repo_cls, \
         patch("backend.document.services.document_service.JobRepository") as job_repo_cls, \
         patch("backend.document.services.document_service.LocalStorageProvider") as storage_cls, \
         patch("backend.document.services.document_service.DocumentEventRepository") as event_repo_cls:

        repo_cls.return_value = AsyncMock()
        job_repo_cls.return_value = AsyncMock()
        storage_cls.return_value = AsyncMock()
        event_repo_cls.return_value = AsyncMock()

        yield DocumentService()

async def test_archive_document_success(service, mock_session):
    doc_id = uuid.uuid4()
    tenant_id = "test-tenant"
    owner_id = uuid.uuid4()

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.status = DocumentStatus.PROCESSED

    service.doc_repo.get_by_id.return_value = mock_doc

    with patch("backend.document.services.document_service.acquire_lock", return_value=DummyAsyncContextManager()) as mock_lock, \
         patch("backend.document.workers.archive.remove_archived_document_vectors_job", MagicMock()) as mock_job:

        await service.archive_document(doc_id, tenant_id, owner_id, mock_session)

        mock_session.commit.assert_called_once()
        mock_job.apply_async.assert_called_once_with(
            args=[str(doc_id), tenant_id], queue="ingestion"
        )

async def test_restore_document_success(service, mock_session):
    doc_id = uuid.uuid4()
    tenant_id = "test-tenant"

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.status = DocumentStatus.ARCHIVED
    mock_doc.latest_version_id = uuid.uuid4()

    service.doc_repo.restore_document.return_value = mock_doc

    with patch("backend.document.services.document_service.acquire_lock", return_value=DummyAsyncContextManager()) as mock_lock, \
         patch("backend.document.workers.archive.restore_archived_document_vectors_job", MagicMock()) as mock_job:

        await service.restore_document(doc_id, tenant_id, mock_session)

        mock_session.commit.assert_called_once()
        mock_job.apply_async.assert_called_once_with(
            args=[str(doc_id), str(mock_doc.latest_version_id), tenant_id], queue="ingestion"
        )

async def test_rollback_to_version_success(service, mock_session):
    doc_id = uuid.uuid4()
    target_version_id = uuid.uuid4()
    tenant_id = "test-tenant"

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.status = DocumentStatus.PROCESSED

    mock_version = MagicMock()
    mock_version.id = target_version_id
    mock_version.document_id = doc_id
    mock_version.storage_object = MagicMock()
    mock_version.version_number = 1

    mock_doc.versions = [mock_version]

    service.doc_repo.get_by_id_with_versions.return_value = mock_doc
    service.doc_repo.get_version_by_id.return_value = mock_version

    # Mock create version flow
    service.storage.clone_object = AsyncMock(return_value=MagicMock())
    service.doc_repo.add_version = AsyncMock()
    mock_job = MagicMock()
    mock_job.id = uuid.uuid4()
    service.job_repo.create = AsyncMock(return_value=mock_job)

    with patch("backend.document.services.document_service.acquire_lock", return_value=DummyAsyncContextManager()), \
         patch("backend.document.workers.ingestion.process_document_job", MagicMock()) as mock_job_task:

        doc, new_version, job = await service.rollback_to_version(
            doc_id, target_version_id, tenant_id, mock_session
        )

        assert doc.status == DocumentStatus.UPLOADED
        mock_session.commit.assert_called()
        mock_job_task.apply_async.assert_called_once()
