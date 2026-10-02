"""Unit tests for D4.5 URL Ingest & Refresh API, normalization, and RBAC / duplicate handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.schemas.errors import DocumentDomainException
from backend.document.services.document_service import DocumentService
from backend.document.services.url_security import (
    SSRFSecurityException,
    ValidatedDestinationDTO,
    normalize_url_identity,
)


class TestUrlNormalization:
    """Unit tests for canonical URL normalization and tracking parameter stripping."""

    def test_basic_lowercasing_and_fragment_removal(self) -> None:
        raw = "HTTPS://Example.COM:443/Docs/Intro#section-1"
        normalized = normalize_url_identity(raw)
        assert normalized == "https://example.com/Docs/Intro"

    def test_strip_default_ports(self) -> None:
        assert normalize_url_identity("http://example.com:80/path") == "http://example.com/path"
        assert normalize_url_identity("https://example.com:443/path") == "https://example.com/path"
        assert normalize_url_identity("https://example.com:8443/path") == "https://example.com:8443/path"

    def test_strip_tracking_parameters(self) -> None:
        raw = (
            "https://example.com/pricing"
            "?utm_source=twitter&utm_medium=social&utm_campaign=launch"
            "&plan=pro&ref=producthunt&gclid=12345"
        )
        normalized = normalize_url_identity(raw)
        assert normalized == "https://example.com/pricing?plan=pro"

    def test_dot_segment_normalization_and_trailing_slash_preservation(self) -> None:
        raw = "https://example.com/a/b/../c/"
        normalized = normalize_url_identity(raw)
        assert normalized == "https://example.com/a/c/"

    def test_deterministic_query_parameter_sorting(self) -> None:
        raw1 = "https://example.com/api?z=1&a=2&m=3"
        raw2 = "https://example.com/api?a=2&m=3&z=1"
        assert normalize_url_identity(raw1) == normalize_url_identity(raw2)
        assert normalize_url_identity(raw1) == "https://example.com/api?a=2&m=3&z=1"

    def test_empty_or_userinfo_url_raises_ssrf_exception(self) -> None:
        with pytest.raises(SSRFSecurityException):
            normalize_url_identity("")

        with pytest.raises(SSRFSecurityException):
            normalize_url_identity("https://admin:secret@example.com/")


class TestUrlIngestService:
    """Unit tests for DocumentService.ingest_url and refresh_url."""

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

    @pytest.mark.asyncio
    async def test_ingest_new_url_success(self, service: DocumentService) -> None:
        mock_session = AsyncMock()
        service.doc_repo.get_by_source_url.return_value = None  # Not existing

        created_doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.PENDING,
        )
        service.doc_repo.create.return_value = created_doc

        created_version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=created_doc.id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="pending_fetch",
            is_active_vector=True,
        )
        service.doc_repo.add_version.return_value = created_version

        created_job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=created_doc.id,
            version_id=created_version.id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
        )
        service.job_repo.create.return_value = created_job

        safe_dest = ValidatedDestinationDTO(
            url="https://example.com/docs",
            scheme="https",
            host="example.com",
            port=443,
            path_and_query="/docs",
            pinned_ip="93.184.216.34",
            resolved_ips=["93.184.216.34"],
        )

        with patch(
            "backend.document.services.url_security.SSRFSafeUrlValidator.validate_destination",
            new_callable=AsyncMock,
            return_value=safe_dest,
        ), patch(
            "backend.document.services.job_dispatcher.JobDispatcher.dispatch_job",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            doc, ver, job, is_existing = await service.ingest_url(
                url="https://Example.com/docs?utm_source=fb",
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert is_existing is False
            assert doc.source_type == "website"
            assert doc.source_url == "https://example.com/docs"
            assert ver.is_active_vector is True
            assert job is not None
            mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_duplicate_url_returns_existing_without_recreating(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        existing_doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=uuid.uuid4(),
        )
        existing_version = DocumentVersion(
            id=existing_doc.latest_version_id,
            document_id=existing_doc.id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="abc",
            is_active_vector=True,
        )
        existing_doc.versions = [existing_version]
        service.doc_repo.get_by_source_url.return_value = existing_doc
        service.doc_repo.get_version_by_id.return_value = existing_version

        safe_dest = ValidatedDestinationDTO(
            url="https://example.com/docs",
            scheme="https",
            host="example.com",
            port=443,
            path_and_query="/docs",
            pinned_ip="93.184.216.34",
            resolved_ips=["93.184.216.34"],
        )

        with patch(
            "backend.document.services.url_security.SSRFSafeUrlValidator.validate_destination",
            new_callable=AsyncMock,
            return_value=safe_dest,
        ):
            doc, _ver, job, is_existing = await service.ingest_url(
                url="https://example.com/docs",
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert is_existing is True
            assert doc.id == existing_doc.id
            assert job is None  # Already READY, no job spawned

    @pytest.mark.asyncio
    async def test_ssrf_forbidden_url_rejected_by_service(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        with pytest.raises(DocumentDomainException) as exc_info:
            await service.ingest_url(
                url="http://127.0.0.1:8080/admin",
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )
        assert exc_info.value.code == "VAL_002"

    @pytest.mark.asyncio
    async def test_refresh_stages_new_version_and_preserves_old(
        self, service: DocumentService
    ) -> None:
        mock_session = AsyncMock()
        doc_id = uuid.uuid4()
        old_version_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            tenant_id="tenant-1",
            filename="docs.html",
            original_filename="https://example.com/docs",
            source_type="website",
            source_url="https://example.com/docs",
            status=DocumentStatus.READY,
            latest_version_id=old_version_id,
        )
        old_version = DocumentVersion(
            id=old_version_id,
            document_id=doc_id,
            version_number=1,
            storage_object_id=uuid.uuid4(),
            content_hash="old_hash",
            is_active_vector=True,
        )
        doc.versions = [old_version]

        service.doc_repo.get_by_id_with_versions.return_value = doc
        service.job_repo.get_by_document_id.return_value = None  # No in-progress job

        staged_version_id = uuid.uuid4()
        staged_version = DocumentVersion(
            id=staged_version_id,
            document_id=doc_id,
            version_number=2,
            storage_object_id=uuid.uuid4(),
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        service.doc_repo.add_version.return_value = staged_version

        created_job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=staged_version_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
        )
        service.job_repo.create.return_value = created_job

        with patch(
            "backend.document.services.job_dispatcher.JobDispatcher.dispatch_job",
            new_callable=AsyncMock,
        ) as mock_dispatch:
            refreshed_doc, staged_ver, _job = await service.refresh_url(
                document_id=doc_id,
                tenant_id="tenant-1",
                owner_user_id=uuid.uuid4(),
                session=mock_session,
            )

            assert refreshed_doc.id == doc_id
            assert staged_ver.version_number == 2
            assert staged_ver.is_active_vector is False  # Staged version remains inactive
            assert old_version.is_active_vector is True  # Active version remains online
            mock_dispatch.assert_called_once()
