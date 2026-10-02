"""Unit tests for D4.6 Celery Ingestion Worker extension for website sources."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.models.storage_object import StorageObject
from backend.document.services.url_security import SSRFSecurityException
from backend.document.services.web_fetcher import FetchedWebResultDTO, WebFetchException
from backend.document.workers.ingestion import _do_process_job


class TestWebsiteWorkerIngestion:
    """Unit tests for website processing in Celery ingestion worker."""

    @pytest.fixture
    def mock_session_factory(self) -> MagicMock:
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None
        return mock_factory

    @pytest.mark.asyncio
    async def test_website_initial_ingest_happy_path(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test full website fetch, snapshot storage, extraction, manifest, and processed transition."""
        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()
        storage_id = uuid.uuid4()
        job_id = uuid.uuid4()
        tenant_id = "tenant-test"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.PENDING,
            latest_version_id=version_id,
        )
        storage_obj = StorageObject(
            id=storage_id,
            provider="local",
            bucket_or_container="raguard-storage",
            object_key=f"tenants/{tenant_id}/documents/{doc_id}/versions/1/original/snapshot.html",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=storage_id,
            content_hash="pending_fetch",
            is_active_vector=True,
        )
        version.storage_object = storage_obj
        doc.versions = [version]

        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            version_id=version_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

        raw_html = b"<html><head><title>Docs</title></head><body><h1>Welcome</h1><p>Documentation text content for testing extraction.</p></body></html>"
        fetch_dto = FetchedWebResultDTO(
            requested_url="https://example.com/docs",
            final_url="https://example.com/docs",
            body_bytes=raw_html,
            content_type="text/html; charset=utf-8",
            content_length=len(raw_html),
            status_code=200,
            headers={"content-type": "text/html"},
            fetched_at=datetime.now(UTC),
        )

        task_instance = MagicMock()

        with patch(
            "backend.document.repositories.JobRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=job,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url",
            new_callable=AsyncMock,
            return_value=fetch_dto,
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_bytes",
            new_callable=AsyncMock,
        ) as mock_save_bytes, patch(
            "backend.document.storage.LocalStorageProvider.save_json",
            new_callable=AsyncMock,
        ), patch(
            "backend.document.storage.LocalStorageProvider.get_stream",
            new_callable=AsyncMock,
        ) as mock_get_stream, patch(
            "backend.document.storage.preflight.StoragePreflightValidator.validate"
        ) as mock_preflight, patch(
            "backend.document.storage.contract.DocumentProcessingContract.verify",
            new_callable=AsyncMock,
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event",
            new_callable=AsyncMock,
        ), patch(
            "backend.core.events.dispatcher.get_dispatcher"
        ) as mock_dispatcher:
            import io
            mock_get_stream.return_value = io.BytesIO(raw_html)
            mock_preflight.return_value = MagicMock(is_valid=True)
            mock_dispatcher.return_value = MagicMock(publish=AsyncMock())

            result = await _do_process_job(task_instance, str(job_id), mock_session_factory)

            assert result["status"] == "success"
            assert result["document_id"] == str(doc_id)
            assert doc.status == DocumentStatus.PROCESSED
            assert doc.final_url == "https://example.com/docs"
            assert doc.last_fetched_at is not None
            assert job.status == "COMPLETED"
            assert mock_save_bytes.called

    @pytest.mark.asyncio
    async def test_website_ssrf_rejection_marks_job_failed(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test that SSRF violation rejects the job and sets failure state."""
        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()
        job_id = uuid.uuid4()
        tenant_id = "tenant-test"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="admin.html",
            original_filename="http://127.0.0.1/admin",
            source_type="website",
            source_url="http://127.0.0.1/admin",
            status=DocumentStatus.PENDING,
            latest_version_id=version_id,
        )
        storage_obj = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="key",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=storage_obj.id,
            content_hash="pending_fetch",
            is_active_vector=True,
        )
        version.storage_object = storage_obj
        doc.versions = [version]

        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            version_id=version_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

        task_instance = MagicMock()

        with patch(
            "backend.document.repositories.JobRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=job,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_versions_by_document_id",
            new_callable=AsyncMock,
            return_value=[version],
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url",
            new_callable=AsyncMock,
            side_effect=SSRFSecurityException(
                error_code="SSRF_FORBIDDEN_IP",
                message="Target destination resolved to forbidden IP 127.0.0.1",
            ),
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event",
            new_callable=AsyncMock,
        ):
            result = await _do_process_job(task_instance, str(job_id), mock_session_factory)

            assert result["status"] == "failed"
            assert result["error_code"] == "VAL_002"
            assert doc.status == DocumentStatus.FAILED
            assert job.status == "FAILED"

    @pytest.mark.asyncio
    async def test_website_refresh_unchanged_content_deduplication(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test that refreshing a website with unchanged content completes without re-indexing."""
        import hashlib

        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        job_id = uuid.uuid4()
        tenant_id = "tenant-test"

        raw_html = b"<html><body>Unchanged content</body></html>"
        content_hash = hashlib.sha256(raw_html).hexdigest()

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
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
            content_hash=content_hash,
            is_active_vector=True,
        )
        v2_storage = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="key_v2",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        v2 = DocumentVersion(
            id=v2_id,
            document_id=doc_id,
            version_number=2,
            storage_object_id=v2_storage.id,
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]

        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            version_id=v2_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

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

        with patch(
            "backend.document.repositories.JobRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=job,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url",
            new_callable=AsyncMock,
            return_value=fetch_dto,
        ):
            result = await _do_process_job(task_instance, str(job_id), mock_session_factory)

            assert result["status"] == "unchanged"
            assert doc.status == DocumentStatus.READY
            assert job.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_website_refresh_failure_preserves_active_document_status(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test that if a background refresh fails, the staged job fails but the active doc remains READY."""
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        job_id = uuid.uuid4()
        tenant_id = "tenant-test"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
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
        v2_storage = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="key_v2",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        v2 = DocumentVersion(
            id=v2_id,
            document_id=doc_id,
            version_number=2,
            storage_object_id=v2_storage.id,
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        v2.storage_object = v2_storage
        doc.versions = [v1, v2]

        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            version_id=v2_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=3,
            max_retries=3,
        )

        task_instance = MagicMock()

        with patch(
            "backend.document.repositories.JobRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=job,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_versions_by_document_id",
            new_callable=AsyncMock,
            return_value=[v1, v2],
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url",
            new_callable=AsyncMock,
            side_effect=WebFetchException(
                error_code="FETCH_HTTP_500",
                message="Target server returned HTTP 500 Internal Server Error",
            ),
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event",
            new_callable=AsyncMock,
        ):
            result = await _do_process_job(task_instance, str(job_id), mock_session_factory)

            assert result["status"] == "failed"
            assert job.status == "FAILED"
            assert doc.status == DocumentStatus.READY  # Main document remains READY for online queries

    @pytest.mark.asyncio
    async def test_website_missing_source_url_fails(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test that website document missing source_url fails fast."""
        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()
        job_id = uuid.uuid4()
        tenant_id = "tenant-test"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="docs.html",
            original_filename="docs.html",
            source_type="website",
            source_url=None,
            status=DocumentStatus.PENDING,
            latest_version_id=version_id,
        )
        storage_obj = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="key",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=storage_obj.id,
            content_hash="pending_fetch",
            is_active_vector=True,
        )
        version.storage_object = storage_obj
        doc.versions = [version]

        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            version_id=version_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

        task_instance = MagicMock()

        with patch(
            "backend.document.repositories.JobRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=job,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_versions_by_document_id",
            new_callable=AsyncMock,
            return_value=[version],
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event",
            new_callable=AsyncMock,
        ):
            result = await _do_process_job(task_instance, str(job_id), mock_session_factory)

            assert result["status"] == "failed"
            assert result["error_code"] == "VAL_002"
            assert doc.status == DocumentStatus.FAILED

    @pytest.mark.asyncio
    async def test_website_recoverable_fetch_triggers_celery_retry(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test that transient fetch error triggers Celery retry with backoff."""
        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()
        job_id = uuid.uuid4()
        tenant_id = "tenant-test"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.PENDING,
            latest_version_id=version_id,
        )
        storage_obj = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="key",
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=storage_obj.id,
            content_hash="pending_fetch",
            is_active_vector=True,
        )
        version.storage_object = storage_obj
        doc.versions = [version]

        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            version_id=version_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

        class CeleryRetryException(Exception):
            pass

        task_instance = MagicMock()
        task_instance.retry.side_effect = CeleryRetryException("Retry requested")

        with patch(
            "backend.document.repositories.JobRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=job,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=doc,
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url",
            new_callable=AsyncMock,
            side_effect=WebFetchException(
                error_code="FETCH_CONNECT_TIMEOUT",
                message="Connect timeout after 5.0s",
            ),
        ):
            with pytest.raises(CeleryRetryException):
                await _do_process_job(task_instance, str(job_id), mock_session_factory)

            assert job.status == "RETRYING"
            assert job.retry_count == 1
            task_instance.retry.assert_called_once()
