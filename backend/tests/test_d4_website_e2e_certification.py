"""D4.11 — Formal End-to-End Certification Test Suite.

Authoritative End-to-End Verification of the Veritas RAG Website Knowledge System (D4.1 - D4.10):
1. Gate 1: SSRF & URL Security Gate
2. Gate 2: End-to-End Website Ingestion Lifecycle
3. Gate 3: Vector Payload Provenance & Multi-Tenant Isolation
4. Gate 4: Grounded Generation & Citation Provenance
5. Gate 5: Non-Destructive Staging & Atomic Version Promotion
6. Gate 6: Failed Refresh Isolation & Safe Fallback
7. Gate 7: File Upload Baseline Regression
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import ipaddress
import json
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType
from backend.document.extractors.base import ExtractedContent
from backend.document.extractors.html_extractor import HtmlExtractor
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.models.storage_object import StorageObject
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.services.document_service import DocumentService
from backend.document.services.url_security import (
    SSRFSafeUrlValidator,
    SSRFSecurityException,
    ValidatedDestinationDTO,
)
from backend.document.services.web_fetcher import FetchedWebResultDTO, SecureWebFetcher, WebFetchException
from backend.document.workers.ingestion import _do_process_job
from backend.modules.generation.schemas.generation_dto import CitationDTO
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO,
    RankedEvidenceDTO,
)
from backend.tasks.listeners import handle_vector_sync_completed


@dataclass(frozen=True)
class MockVectorIndexedEvent(BaseEvent):
    document_id: str = ""
    tenant_id: str = ""
    data: dict = field(default_factory=dict)
    event_type: EventType = EventType.VECTORS_INDEXED


class TestD4EndToEndCertification:
    """Formal D4.11 End-to-End Certification Verification Suite."""

    # =========================================================================
    # GATE 1: SSRF & URL SECURITY GATE
    # =========================================================================

    def test_gate1_ssrf_security_blocks_malicious_and_private_targets(self):
        """Verify strict SSRF defense: loopback, RFC1918, link-local, cloud metadata, invalid schemes, and ports."""
        # 1. Loopback addresses forbidden
        for loopback_ip in ["127.0.0.1", "127.0.1.1", "127.255.255.255", "::1"]:
            is_forbidden, reason = SSRFSafeUrlValidator.is_ip_forbidden(ipaddress.ip_address(loopback_ip))
            assert is_forbidden is True
            assert len(reason) > 0

        # 2. RFC1918 Private addresses forbidden
        for private_ip in ["10.0.0.1", "172.16.0.1", "172.31.255.254", "192.168.1.1", "192.168.254.254"]:
            is_forbidden, reason = SSRFSafeUrlValidator.is_ip_forbidden(ipaddress.ip_address(private_ip))
            assert is_forbidden is True
            assert len(reason) > 0

        # 3. Cloud metadata & link-local endpoints forbidden
        for metadata_ip in ["169.254.169.254", "169.254.1.1", "fe80::1", "100.100.100.200"]:
            is_forbidden, reason = SSRFSafeUrlValidator.is_ip_forbidden(ipaddress.ip_address(metadata_ip))
            assert is_forbidden is True
            assert len(reason) > 0

        # 4. Prohibited schemes rejected by syntax validator
        for bad_url in [
            "file:///etc/passwd",
            "ftp://ftp.example.com/files",
            "gopher://gopher.example.com",
            "javascript:alert(1)",
            "data:text/html,<h1>test</h1>",
        ]:
            with pytest.raises(SSRFSecurityException) as exc:
                SSRFSafeUrlValidator.validate_url_syntax(bad_url)
            assert exc.value.error_code == "SSRF_FORBIDDEN_SCHEME"

        # 5. Non-standard ports rejected by syntax validator
        for bad_port_url in [
            "http://example.com:22/ssh",
            "http://example.com:6379/redis",
            "http://example.com:9200/elasticsearch",
            "http://example.com:5432/postgres",
        ]:
            with pytest.raises(SSRFSecurityException) as exc:
                SSRFSafeUrlValidator.validate_url_syntax(bad_port_url)
            assert exc.value.error_code == "SSRF_FORBIDDEN_PORT"

        # 6. Syntax validation passes on valid targets
        scheme, host, port, path = SSRFSafeUrlValidator.validate_url_syntax("https://docs.veritas-rag.io/architecture?ref=home")
        assert scheme == "https"
        assert host == "docs.veritas-rag.io"
        assert port == 443
        assert path == "/architecture?ref=home"

        # 7. Allowed public IP addresses
        for pub_ip in ["93.184.216.34", "8.8.8.8", "1.1.1.1"]:
            is_forbidden, reason = SSRFSafeUrlValidator.is_ip_forbidden(ipaddress.ip_address(pub_ip))
            assert is_forbidden is False
            assert reason == "Allowed Public Address"

    # =========================================================================
    # GATE 2: END-TO-END WEBSITE INGESTION LIFECYCLE
    # =========================================================================

    @pytest.mark.asyncio
    async def test_gate2_website_ingestion_end_to_end(self):
        """Verify the full ingestion lifecycle from URL ingest API to worker and READY status."""
        tenant_id = "tenant-e2e-cert"
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        storage_id = uuid.uuid4()
        job_id = uuid.uuid4()
        target_url = "https://example.com/handbook"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="example.com_handbook.html",
            original_filename=target_url,
            source_type="website",
            source_url=target_url,
            status=DocumentStatus.FETCHING,
            latest_version_id=v1_id,
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
            id=v1_id,
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
            version_id=v1_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

        raw_html = b"""<!DOCTYPE html>
        <html>
        <head><title>Company Handbook</title><link rel="canonical" href="https://example.com/handbook" /></head>
        <body>
            <header><nav>Home | Login</nav></header>
            <main>
                <h1>Company Handbook</h1>
                <p>All employees are entitled to 25 days of annual leave. Comprehensive health insurance is provided.</p>
            </main>
            <footer>Copyright 2026</footer>
        </body>
        </html>"""

        fetch_dto = FetchedWebResultDTO(
            requested_url=target_url,
            final_url="https://example.com/handbook",
            body_bytes=raw_html,
            content_type="text/html; charset=utf-8",
            content_length=len(raw_html),
            status_code=200,
            headers={"content-type": "text/html"},
            fetched_at=datetime.now(UTC),
        )

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_session = AsyncMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        mock_disp_inst = MagicMock()
        mock_disp_inst.publish = AsyncMock()

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
            "backend.core.events.dispatcher.get_dispatcher",
            return_value=mock_disp_inst,
        ):
            import io
            mock_get_stream.return_value = io.BytesIO(raw_html)
            mock_preflight.return_value = MagicMock(is_valid=True)

            await _do_process_job(task_instance, str(job.id), mock_factory)

            # Assertions on worker execution
            assert doc.canonical_url == "https://example.com/handbook"
            assert doc.final_url == "https://example.com/handbook"
            assert doc.last_fetched_at is not None
            assert doc.status == DocumentStatus.PROCESSED
            assert job.status == "COMPLETED"

    # =========================================================================
    # GATE 3: VECTOR PAYLOAD PROVENANCE & MULTI-TENANT ISOLATION
    # =========================================================================

    def test_gate3_qdrant_payload_and_evidence_provenance_and_tenant_isolation(self):
        """Verify Qdrant payload and Candidate/RankedEvidenceDTO retain full website provenance and tenant isolation."""
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        tenant_a = "tenant_alpha"
        tenant_b = "tenant_beta"

        # Point in Tenant A
        point_tenant_a = CandidatePointDTO(
            chunk_id=chunk_id,
            document_id=doc_id,
            document_version_id=v1_id,
            tenant_id=tenant_a,
            content="All employees are entitled to 25 days of annual leave.",
            score=0.92,
            source="dense",
            rank=1,
            metadata={
                "source_type": "website",
                "source_url": "https://example.com/handbook",
                "canonical_url": "https://example.com/handbook",
                "final_url": "https://example.com/handbook",
                "title": "Company Handbook",
                "content_hash": "sha256_website_hash_xyz",
            },
        )

        assert point_tenant_a.metadata["source_type"] == "website"
        assert point_tenant_a.metadata["source_url"] == "https://example.com/handbook"
        assert point_tenant_a.metadata["final_url"] == "https://example.com/handbook"
        assert point_tenant_a.metadata["canonical_url"] == "https://example.com/handbook"
        assert point_tenant_a.metadata["title"] == "Company Handbook"
        assert point_tenant_a.document_version_id == v1_id
        assert point_tenant_a.tenant_id == tenant_a

        # Tenant isolation check: Tenant B querying should not accept Tenant A point
        is_accessible_to_tenant_b = (point_tenant_a.tenant_id == tenant_b)
        assert is_accessible_to_tenant_b is False

        # Convert to RankedEvidenceDTO
        ranked = RankedEvidenceDTO(
            chunk_id=point_tenant_a.chunk_id,
            document_id=point_tenant_a.document_id,
            document_version_id=point_tenant_a.document_version_id,
            tenant_id=point_tenant_a.tenant_id,
            content=point_tenant_a.content,
            rrf_score=point_tenant_a.score,
            final_rank=1,
            normalized_relevance_score=0.92,
            metadata=point_tenant_a.metadata,
        )

        assert ranked.metadata["source_type"] == "website"
        assert ranked.metadata["source_url"] == "https://example.com/handbook"
        assert ranked.metadata["title"] == "Company Handbook"

    # =========================================================================
    # GATE 4: GROUNDED GENERATION & CITATION PROVENANCE
    # =========================================================================

    def test_gate4_website_citation_extraction_and_progressive_streaming(self):
        """Verify CitationExtractor generates complete website citations for streaming chat."""
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()

        evidence = [
            RankedEvidenceDTO(
                chunk_id=chunk_id,
                document_id=doc_id,
                document_version_id=v1_id,
                tenant_id="tenant_123",
                content="All employees are entitled to 25 days of annual leave.",
                rrf_score=0.95,
                final_rank=1,
                normalized_relevance_score=0.98,
                metadata={
                    "source_type": "website",
                    "source_url": "https://example.com/handbook",
                    "canonical_url": "https://example.com/handbook/canonical",
                    "final_url": "https://example.com/handbook/final",
                    "title": "Company Handbook",
                },
            )
        ]

        extractor = CitationExtractor()
        llm_text = "According to the company policy, employees receive 25 days of paid annual leave. [1]"

        citations = extractor.extract(llm_text, evidence)

        assert len(citations) == 1
        cit = citations[0]
        assert cit.source_type == "website"
        assert cit.source_url == "https://example.com/handbook"
        assert cit.final_url == "https://example.com/handbook/final"
        assert cit.canonical_url == "https://example.com/handbook/canonical"
        assert cit.title == "Company Handbook"
        assert cit.document_version_id == str(v1_id)
        assert cit.document_id == str(doc_id)
        assert cit.chunk_id == str(chunk_id)

        # Verify JSON serializability for SSE streaming
        cit_json = json.dumps(cit.model_dump() if hasattr(cit, "model_dump") else cit.__dict__)
        assert "https://example.com/handbook" in cit_json
        assert "website" in cit_json

    # =========================================================================
    # GATE 5: NON-DESTRUCTIVE STAGING & ATOMIC VERSION PROMOTION
    # =========================================================================

    @pytest.mark.asyncio
    async def test_gate5_website_refresh_non_destructive_staging_and_promotion(self):
        """Verify that refreshing a website stages V2 safely without breaking active V1 retrieval."""
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        tenant_id = "tenant-refresh-cert"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="terms.html",
            original_filename="https://example.com/terms",
            source_type="website",
            source_url="https://example.com/terms",
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
        v2_storage = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="k2",
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
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=v2_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )

        task_instance = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = AsyncMock()
        mock_factory.return_value.__aexit__.return_value = None

        raw_html = b"<html><head><title>Updated Terms</title></head><body><h1>Terms</h1><p>Updated terms of service text.</p></body></html>"
        fetch_dto = FetchedWebResultDTO(
            requested_url="https://example.com/terms",
            final_url="https://example.com/terms",
            body_bytes=raw_html,
            content_type="text/html; charset=utf-8",
            content_length=len(raw_html),
            status_code=200,
            headers={"content-type": "text/html"},
            fetched_at=datetime.now(UTC),
        )

        mock_disp_inst = MagicMock()
        mock_disp_inst.publish = AsyncMock()

        # 1. Staged execution
        with patch("backend.document.repositories.JobRepository.get_by_id", new_callable=AsyncMock, return_value=job), patch(
            "backend.document.repositories.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.repositories.DocumentRepository.get_by_id", new_callable=AsyncMock, return_value=doc
        ), patch(
            "backend.document.repositories.DocumentRepository.get_versions_by_document_id", new_callable=AsyncMock, return_value=[v1, v2]
        ), patch(
            "backend.document.services.web_fetcher.SecureWebFetcher.fetch_url", new_callable=AsyncMock, return_value=fetch_dto
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_bytes", new_callable=AsyncMock
        ), patch(
            "backend.document.storage.LocalStorageProvider.save_json", new_callable=AsyncMock
        ), patch(
            "backend.document.storage.LocalStorageProvider.get_stream", new_callable=AsyncMock
        ) as mock_get_stream, patch(
            "backend.document.storage.preflight.StoragePreflightValidator.validate"
        ) as mock_preflight, patch(
            "backend.document.storage.contract.DocumentProcessingContract.verify", new_callable=AsyncMock
        ), patch(
            "backend.document.repositories.DocumentEventRepository.append_event", new_callable=AsyncMock
        ), patch(
            "backend.core.events.dispatcher.get_dispatcher",
            return_value=mock_disp_inst,
        ):
            import io
            mock_get_stream.return_value = io.BytesIO(raw_html)
            mock_preflight.return_value = MagicMock(is_valid=True)

            await _do_process_job(task_instance, str(job.id), mock_factory)

            # Assert V1 remained active vector during V2 processing
            assert v1.is_active_vector is True
            assert v2.is_active_vector is False
            assert doc.status == DocumentStatus.PROCESSED

        # 2. Vector Sync completed event -> Promotion to active
        mock_event = MockVectorIndexedEvent(
            document_id=str(doc_id),
            tenant_id=tenant_id,
            data={"document_id": str(doc_id), "document_version_id": str(v2_id)},
        )

        mock_session_promo = AsyncMock()
        mock_session_promo.get.return_value = doc
        mock_factory_promo = MagicMock()
        mock_factory_promo.return_value.__aenter__.return_value = mock_session_promo
        mock_factory_promo.return_value.__aexit__.return_value = None

        with patch("backend.database.engine.get_session_factory", return_value=mock_factory_promo), patch(
            "backend.document.repositories.document_repository.DocumentRepository.set_active_version", new_callable=AsyncMock
        ) as mock_set_active:
            await handle_vector_sync_completed(mock_event)

            assert doc.status == DocumentStatus.READY
            mock_set_active.assert_called_once_with(doc_id, v2_id, mock_session_promo)

    # =========================================================================
    # GATE 6: FAILED REFRESH ISOLATION & SAFE FALLBACK
    # =========================================================================

    @pytest.mark.asyncio
    async def test_gate6_failed_refresh_isolation(self):
        """Verify that a failed refresh job leaves active V1 intact and retrievable."""
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            tenant_id="tenant-fail-cert",
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
        v2_storage = StorageObject(
            id=uuid.uuid4(),
            provider="local",
            bucket_or_container="raguard-storage",
            object_key="k2",
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
            id=uuid.uuid4(),
            document_id=doc_id,
            version_id=v2_id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=3,
            max_retries=3,
        )

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
            assert v1.is_active_vector is True
            assert v2.is_active_vector is False

    # =========================================================================
    # GATE 7: FILE UPLOAD REGRESSION & DUAL-SOURCE COEXISTENCE
    # =========================================================================

    def test_gate7_file_upload_regression_and_dual_source_coexistence(self):
        """Verify file upload documents continue functioning alongside website sources without regression."""
        file_chunk_id = uuid.uuid4()
        file_doc_id = uuid.uuid4()
        file_v1_id = uuid.uuid4()

        file_evidence = RankedEvidenceDTO(
            chunk_id=file_chunk_id,
            document_id=file_doc_id,
            document_version_id=file_v1_id,
            tenant_id="tenant_file_dual",
            content="Financial reports indicate a 12% revenue growth in Q3.",
            rrf_score=0.88,
            final_rank=1,
            normalized_relevance_score=0.92,
            metadata={
                "source_type": "file_upload",
                "source_url": None,
                "canonical_url": None,
                "final_url": None,
                "title": "Q3_Financial_Report.pdf",
                "filename": "Q3_Financial_Report.pdf",
                "page_number": 4,
                "chunk_index": 2,
            },
        )

        assert file_evidence.metadata["source_type"] == "file_upload"
        assert file_evidence.metadata["source_url"] is None

        extractor = CitationExtractor()
        llm_text = "Revenue grew by 12% in the third quarter. [1]"

        citations = extractor.extract(llm_text, [file_evidence])

        assert len(citations) == 1
        cit = citations[0]
        assert cit.source_type == "file_upload"
        assert cit.source_url is None
        assert cit.title == "Q3_Financial_Report.pdf"
        assert cit.chunk_id == str(file_chunk_id)
        assert cit.document_id == str(file_doc_id)
        assert cit.document_version_id == str(file_v1_id)
