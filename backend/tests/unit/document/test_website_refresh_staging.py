"""Unit tests for D4.7 Website Refresh & Staging lifecycle.

Covers all 16 required test cases for version staging, non-destructive concurrency,
failure isolation, and atomic vector promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.models.storage_object import StorageObject
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.schemas.errors import DocumentDomainException
from backend.document.services.document_service import DocumentService
from backend.document.services.web_fetcher import FetchedWebResultDTO, WebFetchException
from backend.document.workers.ingestion import _do_process_job
from backend.tasks.listeners import handle_vector_sync_completed


@dataclass(frozen=True)
class MockVectorIndexedEvent(BaseEvent):
    document_id: str = ""
    tenant_id: str = ""
    data: dict = field(default_factory=dict)
    event_type: EventType = EventType.VECTORS_INDEXED


class TestWebsiteRefreshStaging:
    """Comprehensive test suite for D4.7 website refresh and staging."""

    @pytest.fixture
    def mock_doc_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_job_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_storage_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_event_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        mock_doc_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_storage_repo: AsyncMock,
        mock_event_repo: AsyncMock,
    ) -> DocumentService:
        return DocumentService(
            doc_repo=mock_doc_repo,
            job_repo=mock_job_repo,
            storage_repo=mock_storage_repo,
            event_repo=mock_event_repo,
        )

    # 1. Staged version is created with is_active_vector=False
    @pytest.mark.asyncio
    async def test_refresh_website_creates_staged_version_with_active_flag_false(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=v1_id,
        )
        v1 = DocumentVersion(
            id=v1_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="hash1",
            is_active_vector=True,
        )
        doc.versions = [v1]

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = None

        staged_v = DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_number=2,
            storage_object_id=uuid.uuid4(),
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        service.doc_repo.add_version.return_value = staged_v
        service.job_repo.create.return_value = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=staged_v.id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
        )

        with patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", new_callable=AsyncMock):
            _, staged_result, _ = await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert staged_result.is_active_vector is False

    # 2. Existing active version remains online
    @pytest.mark.asyncio
    async def test_refresh_preserves_active_version_online(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=v1_id,
        )
        v1 = DocumentVersion(
            id=v1_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="hash1",
            is_active_vector=True,
        )
        doc.versions = [v1]

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = None

        staged_v = DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_number=2,
            storage_object_id=uuid.uuid4(),
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        service.doc_repo.add_version.return_value = staged_v
        service.job_repo.create.return_value = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=staged_v.id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
        )

        with patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", new_callable=AsyncMock):
            await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert v1.is_active_vector is True

    # 3. Refreshing non-website document raises domain exception
    @pytest.mark.asyncio
    async def test_refresh_non_website_document_raises_domain_exception(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="sample.pdf",
            original_filename="sample.pdf",
            source_type="file_upload",
            source_url=None,
            status=DocumentStatus.READY,
        )
        service.doc_repo.get_by_id_with_versions.return_value = doc

        with pytest.raises(DocumentDomainException) as exc_info:
            await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )
        assert exc_info.value.code == "SYS_001"

    # 4. Refreshing non-existent document raises domain exception
    @pytest.mark.asyncio
    async def test_refresh_non_existent_document_raises_domain_exception(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        service.doc_repo.get_by_id_with_versions.return_value = None

        with pytest.raises(DocumentDomainException) as exc_info:
            await service.refresh_url(
                document_id=uuid.uuid4(),
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )
        assert exc_info.value.code == "SYS_001"

    # 5. Refresh concurrency lock rejects parallel duplicate jobs
    @pytest.mark.asyncio
    async def test_refresh_concurrency_lock_rejects_parallel_refresh(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.FETCHING,
            latest_version_id=v1_id,
        )
        v1 = DocumentVersion(
            id=v1_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="hash1",
            is_active_vector=True,
        )
        doc.versions = [v1]

        active_job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=v1_id,
            status="FETCHING",
            current_step="fetch",
        )

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = active_job
        service.doc_repo.get_version_by_id.return_value = v1

        _, ret_version, ret_job = await service.refresh_url(
            document_id=doc_id,
            tenant_id="tenant-1",
            owner_user_id=uuid.uuid4(),
            session=mock_session,
        )

        assert ret_job.id == active_job.id
        assert ret_version.id == v1_id
        service.doc_repo.add_version.assert_not_called()

    # 6. Version number monotonically increments
    @pytest.mark.asyncio
    async def test_refresh_version_number_monotonically_increments(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
        )
        v1 = DocumentVersion(id=uuid.uuid4(), document_id=doc_id, version_number=1, storage_object_id=uuid.uuid4(), content_hash="h1", is_active_vector=False)
        v2 = DocumentVersion(id=uuid.uuid4(), document_id=doc_id, version_number=2, storage_object_id=uuid.uuid4(), content_hash="h2", is_active_vector=True)
        doc.versions = [v1, v2]

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = None

        captured_version: list[DocumentVersion] = []

        async def capture_add_version(v: DocumentVersion, s: AsyncMock) -> DocumentVersion:
            captured_version.append(v)
            return v

        service.doc_repo.add_version.side_effect = capture_add_version
        service.job_repo.create.return_value = ProcessingJob(
            id=uuid.uuid4(), document_id=doc_id, version_id=uuid.uuid4(), status=DocumentStatus.PENDING, current_step="fetch"
        )

        with patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", new_callable=AsyncMock):
            await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert len(captured_version) == 1
            assert captured_version[0].version_number == 3

    # 7. Snapshot storage object created under version path
    @pytest.mark.asyncio
    async def test_refresh_creates_snapshot_storage_object(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
        )
        v1 = DocumentVersion(id=uuid.uuid4(), document_id=doc_id, version_number=1, storage_object_id=uuid.uuid4(), content_hash="h1", is_active_vector=True)
        doc.versions = [v1]

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = None

        captured_storage: list[StorageObject] = []

        async def capture_storage(s: StorageObject, sess: AsyncMock) -> StorageObject:
            captured_storage.append(s)
            return s

        service.storage_repo.create.side_effect = capture_storage
        service.doc_repo.add_version.return_value = DocumentVersion(
            id=uuid.uuid4(), document_id=doc_id, version_number=2, storage_object_id=uuid.uuid4(), content_hash="pending_fetch", is_active_vector=False
        )
        service.job_repo.create.return_value = ProcessingJob(
            id=uuid.uuid4(), document_id=doc_id, version_id=uuid.uuid4(), status=DocumentStatus.PENDING, current_step="fetch"
        )

        with patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", new_callable=AsyncMock):
            await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert len(captured_storage) == 1
            assert "v2/original/snapshot.html" in captured_storage[0].object_key
            assert captured_storage[0].mime_type == "text/html"

    # 8. Same content hash short circuits
    @pytest.mark.asyncio
    async def test_refresh_same_content_hash_short_circuits_gracefully(self) -> None:
        import hashlib
        raw = b"<html><body>Same content</body></html>"
        chash = hashlib.sha256(raw).hexdigest()

        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=v1_id,
        )
        v1 = DocumentVersion(id=v1_id, document_id=doc_id, version_number=1, storage_object_id=uuid.uuid4(), content_hash=chash, is_active_vector=True)
        v2_storage = StorageObject(id=uuid.uuid4(), provider="local", bucket_or_container="raguard-storage", object_key="k2", file_size_bytes=0, mime_type="text/html", checksum_sha256="pending_fetch")
        v2 = DocumentVersion(id=v2_id, document_id=doc_id, version_number=2, storage_object_id=v2_storage.id, content_hash="pending_fetch", is_active_vector=False)
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]

        job = ProcessingJob(id=uuid.uuid4(), document_id=doc_id, version_id=v2_id, status=DocumentStatus.PENDING, current_step="fetch", retry_count=0, max_retries=3)

        fetch_dto = FetchedWebResultDTO(
            requested_url="https://example.com/docs",
            final_url="https://example.com/docs",
            body_bytes=raw,
            content_type="text/html",
            content_length=len(raw),
            status_code=200,
            headers={},
            fetched_at=datetime.now(UTC),
        )

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = AsyncMock()
        mock_factory.return_value.__aexit__.return_value = None

        with patch("backend.document.repositories.JobRepository.get_by_id", new_callable=AsyncMock, return_value=job), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url", new_callable=AsyncMock, return_value=fetch_dto
        ):
            res = await _do_process_job(task_instance, str(job.id), mock_factory)
            assert res["status"] == "unchanged"
            assert doc.status == DocumentStatus.READY
            assert job.status == "COMPLETED"

    # 9. Updated content proceeds through extraction
    @pytest.mark.asyncio
    async def test_refresh_updated_content_proceeds_to_extraction_and_manifest(self) -> None:
        raw = b"<html><head><title>Updated</title></head><body><p>Updated content text for testing.</p></body></html>"

        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=v1_id,
        )
        v1 = DocumentVersion(id=v1_id, document_id=doc_id, version_number=1, storage_object_id=uuid.uuid4(), content_hash="old_hash", is_active_vector=True)
        v2_storage = StorageObject(id=uuid.uuid4(), provider="local", bucket_or_container="raguard-storage", object_key="k2", file_size_bytes=0, mime_type="text/html", checksum_sha256="pending_fetch")
        v2 = DocumentVersion(id=v2_id, document_id=doc_id, version_number=2, storage_object_id=v2_storage.id, content_hash="pending_fetch", is_active_vector=False)
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]

        job = ProcessingJob(id=uuid.uuid4(), document_id=doc_id, version_id=v2_id, status=DocumentStatus.PENDING, current_step="fetch", retry_count=0, max_retries=3)

        fetch_dto = FetchedWebResultDTO(
            requested_url="https://example.com/docs",
            final_url="https://example.com/docs",
            body_bytes=raw,
            content_type="text/html",
            content_length=len(raw),
            status_code=200,
            headers={},
            fetched_at=datetime.now(UTC),
        )

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = AsyncMock()
        mock_factory.return_value.__aexit__.return_value = None

        import io
        with patch("backend.document.repositories.JobRepository.get_by_id", new_callable=AsyncMock, return_value=job), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url", new_callable=AsyncMock, return_value=fetch_dto
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_bytes", new_callable=AsyncMock
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_json", new_callable=AsyncMock
        ), patch(
            "backend.document.storage.LocalStorageProvider.get_stream", new_callable=AsyncMock, return_value=io.BytesIO(raw)
        ), patch(
            "backend.document.storage.preflight.StoragePreflightValidator.validate", return_value=MagicMock(is_valid=True)
        ), patch(
            "backend.document.storage.contract.DocumentProcessingContract.verify", new_callable=AsyncMock
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event", new_callable=AsyncMock
        ), patch(
            "backend.core.events.dispatcher.get_dispatcher", return_value=MagicMock(publish=AsyncMock())
        ):
            res = await _do_process_job(task_instance, str(job.id), mock_factory)
            assert res["status"] == "success"
            assert doc.status == DocumentStatus.PROCESSED

    # 10. Failed refresh does not mutate active version flag
    @pytest.mark.asyncio
    async def test_refresh_failure_does_not_mutate_active_version_flag(self) -> None:
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(id=doc_id, tenant_id="tenant-1", filename="docs.html", original_filename="https://example.com/docs", source_type="website", source_url="https://example.com/docs", status=DocumentStatus.READY, latest_version_id=v1_id)
        v1 = DocumentVersion(id=v1_id, document_id=doc_id, version_number=1, storage_object_id=uuid.uuid4(), content_hash="h1", is_active_vector=True)
        v2_storage = StorageObject(id=uuid.uuid4(), provider="local", bucket_or_container="raguard-storage", object_key="k2", file_size_bytes=0, mime_type="text/html", checksum_sha256="pending_fetch")
        v2 = DocumentVersion(id=v2_id, document_id=doc_id, version_number=2, storage_object_id=v2_storage.id, content_hash="pending_fetch", is_active_vector=False)
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]

        job = ProcessingJob(id=uuid.uuid4(), document_id=doc_id, version_id=v2_id, status=DocumentStatus.PENDING, current_step="fetch", retry_count=3, max_retries=3)

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = AsyncMock()
        mock_factory.return_value.__aexit__.return_value = None

        with patch("backend.document.repositories.JobRepository.get_by_id", new_callable=AsyncMock, return_value=job), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.repositories.DocumentRepository.get_versions_by_document_id", new_callable=AsyncMock, return_value=[v1, v2]
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url", new_callable=AsyncMock, side_effect=WebFetchException(error_code="FETCH_404", message="Not found")
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event", new_callable=AsyncMock
        ):
            await _do_process_job(task_instance, str(job.id), mock_factory)
            assert v1.is_active_vector is True
            assert v2.is_active_vector is False

    # 11. Failed refresh preserves document READY status
    @pytest.mark.asyncio
    async def test_refresh_failure_preserves_document_ready_status(self) -> None:
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(id=doc_id, tenant_id="tenant-1", filename="docs.html", original_filename="https://example.com/docs", source_type="website", source_url="https://example.com/docs", status=DocumentStatus.READY, latest_version_id=v1_id)
        v1 = DocumentVersion(id=v1_id, document_id=doc_id, version_number=1, storage_object_id=uuid.uuid4(), content_hash="h1", is_active_vector=True)
        v2_storage = StorageObject(id=uuid.uuid4(), provider="local", bucket_or_container="raguard-storage", object_key="k2", file_size_bytes=0, mime_type="text/html", checksum_sha256="pending_fetch")
        v2 = DocumentVersion(id=v2_id, document_id=doc_id, version_number=2, storage_object_id=v2_storage.id, content_hash="pending_fetch", is_active_vector=False)
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]

        job = ProcessingJob(id=uuid.uuid4(), document_id=doc_id, version_id=v2_id, status=DocumentStatus.PENDING, current_step="fetch", retry_count=3, max_retries=3)

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = AsyncMock()
        mock_factory.return_value.__aexit__.return_value = None

        with patch("backend.document.repositories.JobRepository.get_by_id", new_callable=AsyncMock, return_value=job), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.repositories.DocumentRepository.get_versions_by_document_id", new_callable=AsyncMock, return_value=[v1, v2]
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url", new_callable=AsyncMock, side_effect=WebFetchException(error_code="FETCH_500", message="Server Error")
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event", new_callable=AsyncMock
        ):
            await _do_process_job(task_instance, str(job.id), mock_factory)
            assert doc.status == DocumentStatus.READY
            assert job.status == "FAILED"

    # 12. Vector sync promotion activates staged version atomically
    @pytest.mark.asyncio
    async def test_refresh_promotion_activates_staged_version_atomically(self) -> None:
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(id=doc_id, tenant_id="tenant-1", filename="docs.html", status=DocumentStatus.VECTOR_SYNC, latest_version_id=v1_id)

        mock_event = MockVectorIndexedEvent(
            document_id=str(doc_id),
            tenant_id="tenant-1",
            data={"document_id": str(doc_id), "document_version_id": str(v2_id)},
        )

        mock_session = AsyncMock()
        mock_session.get.return_value = doc

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        with patch("backend.database.engine.get_session_factory", return_value=mock_factory), patch(
            "backend.document.repositories.document_repository.DocumentRepository.set_active_version", new_callable=AsyncMock
        ) as mock_set_active:
            await handle_vector_sync_completed(mock_event)

            assert doc.status == DocumentStatus.READY
            mock_set_active.assert_called_once_with(doc_id, v2_id, mock_session)

    # 13. Promotion updates doc.latest_version_id
    @pytest.mark.asyncio
    async def test_refresh_promotion_updates_doc_latest_version_id(self) -> None:
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(id=doc_id, tenant_id="tenant-1", filename="docs.html", status=DocumentStatus.VECTOR_SYNC, latest_version_id=v1_id)

        mock_event = MockVectorIndexedEvent(
            document_id=str(doc_id),
            tenant_id="tenant-1",
            data={"document_id": str(doc_id), "document_version_id": str(v2_id)},
        )

        mock_session = AsyncMock()
        mock_session.get.return_value = doc

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        with patch("backend.database.engine.get_session_factory", return_value=mock_factory), patch(
            "backend.document.repositories.document_repository.DocumentRepository.set_active_version", new_callable=AsyncMock
        ):
            await handle_vector_sync_completed(mock_event)

            assert doc.latest_version_id == v2_id

    # 14. set_active_version deactivates all older versions
    @pytest.mark.asyncio
    async def test_set_active_version_deactivates_older_versions(self) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()
        target_v_id = uuid.uuid4()

        repo = DocumentRepository()
        await repo.set_active_version(doc_id, target_v_id, mock_session)

        # Verify two execute statements (deactivate all, activate target)
        assert mock_session.execute.call_count == 2
        assert mock_session.flush.called

    # 15. Status endpoint shows fetching progress percentage
    @pytest.mark.asyncio
    async def test_status_endpoint_shows_fetching_progress(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()

        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.FETCHING,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=uuid.uuid4(),
            status=DocumentStatus.FETCHING,
            current_step="fetch",
        )

        service.doc_repo.get_by_id.return_value = doc
        service.job_repo.get_by_document_id.return_value = job

        status_res = await service.get_status(doc_id, "tenant-1", mock_session)
        assert status_res is not None
        assert status_res.status == DocumentStatus.FETCHING
        assert status_res.current_step == "fetch"
        assert status_res.progress_percent == 15

    # 16. Full refresh lifecycle sequence
    @pytest.mark.asyncio
    async def test_full_refresh_lifecycle_sequence(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()

        # Initial document at V1 READY
        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=v1_id,
        )
        v1 = DocumentVersion(
            id=v1_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="h1",
            is_active_vector=True,
        )
        doc.versions = [v1]

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = None

        v2_storage = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="v2_key",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        service.storage_repo.create.return_value = v2_storage

        v2 = DocumentVersion(
            id=v2_id,
            document_id=doc_id,
            version_number=2,
            storage_object_id=v2_storage.id,
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        service.doc_repo.add_version.return_value = v2

        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=v2_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
        )
        service.job_repo.create.return_value = job

        # 1. Trigger refresh
        with patch("backend.document.services.job_dispatcher.JobDispatcher.dispatch_job", new_callable=AsyncMock):
            ref_doc, staged_v, _ = await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )
            assert ref_doc.id == doc_id
            assert staged_v.version_number == 2
            assert staged_v.is_active_vector is False

        # 2. Worker executes job for V2
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]
        job.retry_count = 0
        job.max_retries = 3

        raw_html = b"<html><head><title>V2</title></head><body><p>Version 2 new content text.</p></body></html>"
        fetch_dto = FetchedWebResultDTO(
            requested_url="https://example.com/docs",
            final_url="https://example.com/docs",
            body_bytes=raw_html,
            content_type="text/html",
            content_length=len(raw_html),
            status_code=200,
            headers={},
            fetched_at=datetime.now(UTC),
        )

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = AsyncMock()
        mock_factory.return_value.__aexit__.return_value = None

        import io
        with patch("backend.document.repositories.JobRepository.get_by_id", new_callable=AsyncMock, return_value=job), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url", new_callable=AsyncMock, return_value=fetch_dto
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_bytes", new_callable=AsyncMock
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_json", new_callable=AsyncMock
        ), patch(
            "backend.document.storage.LocalStorageProvider.get_stream", new_callable=AsyncMock, return_value=io.BytesIO(raw_html)
        ), patch(
            "backend.document.storage.preflight.StoragePreflightValidator.validate", return_value=MagicMock(is_valid=True)
        ), patch(
            "backend.document.storage.contract.DocumentProcessingContract.verify", new_callable=AsyncMock
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event", new_callable=AsyncMock
        ), patch(
            "backend.core.events.dispatcher.get_dispatcher", return_value=MagicMock(publish=AsyncMock())
        ):
            worker_res = await _do_process_job(task_instance, str(job.id), mock_factory)
            assert worker_res["status"] == "success"
            assert doc.status == DocumentStatus.PROCESSED
