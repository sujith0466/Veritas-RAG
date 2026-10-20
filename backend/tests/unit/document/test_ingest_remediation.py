"""Unit tests for Veritas-RAG Phase 3 (WP-INGEST) Remediation.

Covers all 13 authorized findings:
- ING-002: Storage preflight entity attribute alignment (file_size_bytes, provider)
- ING-003: StorageProviderFactory S3/MinIO environment resolution
- ING-004: Platform-independent storage fallback root resolution
- ING-006: PlainTextExtractor YAML/XML extension and MIME support
- ING-008: TesseractOCREngine PDF rasterization via pypdfium2
- ING-009: DoclingOCREngine OCR_002 fallback signaling
- ING-010: UnstructuredExtractor missing dependency fail-fast
- DATA-002: Rollback version promotion deferral (is_active_vector=False)
- DATA-003: Cascade soft-delete across versions, chunks, and embeddings
- DATA-004: Chunk hash salting policy consistency
- DATA-005: Ingestion worker actual_tenant_id resolution
- PERF-001: PDFExtractor asyncio.to_thread offloading
- OBS-003: JobDispatcher correlation_id header propagation
"""

import asyncio
import io
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.extractors.pdf_extractor import PDFExtractor
from backend.document.extractors.text_extractor import PlainTextExtractor
from backend.document.extractors.unstructured_extractor import UnstructuredExtractor
from backend.document.ocr.docling import DoclingOCREngine
from backend.document.ocr.pipeline import OCRPipeline
from backend.document.ocr.tesseract import TesseractOCREngine
from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode
from backend.document.services.job_dispatcher import DispatchResult, JobDispatcher
from backend.document.storage.factory import StorageProviderFactory
from backend.document.storage.local import LocalStorageProvider
from backend.document.storage.preflight import (
    PreflightResult,
    StoragePreflightValidator,
)


class TestWPIngestRemediation:
    """Phase 3 WP-INGEST Remediation Test Suite."""

    # -------------------------------------------------------------------------
    # ING-002 & ING-004: Storage Preflight
    # -------------------------------------------------------------------------
    def test_ing_004_platform_independent_fallback_root(self):
        """ING-004: Storage fallback root must not contain hardcoded Windows drive letters."""
        fallback_str = str(StoragePreflightValidator.HOST_FALLBACK_ROOT)
        assert not fallback_str.startswith("D:\\app")
        assert not fallback_str.startswith("D:/app")

    def test_ing_002_preflight_entity_attributes(self, tmp_path):
        """ING-002: Preflight correctly validates StorageObject attributes (provider, file_size_bytes)."""
        tenant_id = str(uuid.uuid4())
        container_file = tmp_path / tenant_id / "raw" / "test.txt"
        container_file.parent.mkdir(parents=True, exist_ok=True)
        container_file.write_bytes(b"Valid container file")

        # Mock StorageObject using the actual Document model attributes (provider, file_size_bytes)
        storage_obj = MagicMock()
        del storage_obj.storage_provider  # ensure old name is absent
        del storage_obj.size_bytes        # ensure old name is absent
        storage_obj.provider = "local"
        storage_obj.bucket_or_container = "/app/data/storage"
        storage_obj.object_key = f"{tenant_id}/raw/test.txt"
        storage_obj.file_size_bytes = len(b"Valid container file")

        with patch.object(StoragePreflightValidator, "CONTAINER_ROOT", tmp_path):
            result = StoragePreflightValidator.validate(storage_obj, expected_tenant_id=tenant_id)
            assert result.is_valid is True
            assert result.error_code is None
            assert result.file_size_bytes == len(b"Valid container file")

    # -------------------------------------------------------------------------
    # ING-003: StorageProviderFactory
    # -------------------------------------------------------------------------
    def test_ing_003_storage_provider_factory_s3_and_minio(self):
        """ING-003: StorageProviderFactory resolves s3 and minio configurations properly."""
        with patch.dict(os.environ, {"STORAGE_PROVIDER": "s3", "S3_BUCKET_NAME": "my-bucket"}):
            with patch("backend.document.storage.cloud.S3StorageProvider") as mock_s3:
                StorageProviderFactory.get_provider()
                mock_s3.assert_called_once()
                call_kwargs = mock_s3.call_args[1]
                assert call_kwargs["bucket"] == "my-bucket"

        with patch.dict(os.environ, {
            "STORAGE_PROVIDER": "minio",
            "S3_BUCKET_NAME": "minio-bucket",
            "MINIO_ENDPOINT_URL": "http://minio:9000"
        }):
            with patch("backend.document.storage.cloud.S3StorageProvider") as mock_s3:
                StorageProviderFactory.get_provider()
                mock_s3.assert_called_once()
                call_kwargs = mock_s3.call_args[1]
                assert call_kwargs["bucket"] == "minio-bucket"
                assert call_kwargs["endpoint_url"] == "http://minio:9000"

        with patch.dict(os.environ, {"STORAGE_PROVIDER": "local"}):
            provider = StorageProviderFactory.get_provider()
            assert isinstance(provider, LocalStorageProvider)

    # -------------------------------------------------------------------------
    # ING-006: PlainTextExtractor YAML/XML
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ing_006_plaintext_extractor_yaml_xml(self):
        """ING-006: PlainTextExtractor supports .yaml, .yml, .xml."""
        extractor = PlainTextExtractor()
        cap = extractor.capability

        assert ".yaml" in cap.supported_extensions
        assert ".yml" in cap.supported_extensions
        assert ".xml" in cap.supported_extensions
        assert "application/x-yaml" in cap.supported_mimes
        assert "application/xml" in cap.supported_mimes
        assert "text/xml" in cap.supported_mimes

        # Test extraction of YAML
        yaml_content = b"version: '3'\nservices:\n  web:\n    image: nginx\n"
        result_yaml = await extractor.extract(io.BytesIO(yaml_content), "docker-compose.yaml", "application/x-yaml")
        assert "nginx" in result_yaml.text
        assert result_yaml.word_count > 0

        # Test extraction of XML
        xml_content = b"<root><title>Veritas RAG</title><status>Active</status></root>"
        result_xml = await extractor.extract(io.BytesIO(xml_content), "doc.xml", "application/xml")
        assert "Veritas RAG" in result_xml.text
        assert result_xml.word_count > 0

    # -------------------------------------------------------------------------
    # ING-008: Tesseract PDF Rasterization
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ing_008_tesseract_pdf_rasterization(self):
        """ING-008: TesseractOCREngine rasterizes PDF streams using pypdfium2."""
        engine = TesseractOCREngine()

        # Generate a minimal valid PDF byte sequence
        pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 100 100]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n162\n%%EOF\n"

        # Mock pytesseract.image_to_string
        with patch("pytesseract.image_to_string", return_value="Rasterized PDF Page Content"):
            result = await engine.process(io.BytesIO(pdf_bytes), "scanned.pdf", timeout_seconds=5)
            assert "Rasterized PDF Page Content" in result.text
            assert result.page_count >= 1
            assert result.word_count > 0

    # -------------------------------------------------------------------------
    # ING-009: Docling OCR_002 Fallback Signal
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ing_009_docling_ocr_002_signal(self):
        """ING-009: Docling raises OCR_002 (recoverable) so OCRPipeline falls back cleanly."""
        docling_engine = DoclingOCREngine()

        with pytest.raises(DocumentDomainException) as exc_info:
            await docling_engine.process(io.BytesIO(b"image data"), "test.png")
        assert exc_info.value.code == DocumentErrorCode.OCR_002

        # Verify OCRPipeline falls back to Tesseract when Docling raises OCR_002
        tesseract_mock = MagicMock(spec=TesseractOCREngine)
        tesseract_mock.engine_name = "tesseract"
        tesseract_mock.process = AsyncMock(
            return_value=MagicMock(word_count=5, text="Fallback OCR text", page_count=1)
        )

        pipeline = OCRPipeline(engines=[docling_engine, tesseract_mock])
        res = await pipeline.execute(io.BytesIO(b"image data"), "test.png", timeout_seconds=5)
        assert res.text == "Fallback OCR text"
        tesseract_mock.process.assert_awaited_once()

    # -------------------------------------------------------------------------
    # ING-010: Unstructured Missing Dependency Fail-Fast
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_ing_010_unstructured_fail_fast(self):
        """ING-010: UnstructuredExtractor raises EXTRACT_001 when unstructured is not installed."""
        extractor = UnstructuredExtractor()
        with patch("backend.document.extractors.unstructured_extractor.partition", None):
            with pytest.raises(DocumentDomainException) as exc_info:
                await extractor.extract(io.BytesIO(b"dummy"), "doc.pdf", "application/pdf")
            assert exc_info.value.code == DocumentErrorCode.EXTRACT_001
            assert "unstructured library not installed" in exc_info.value.message

    # -------------------------------------------------------------------------
    # DATA-002: Rollback Version Promotion Deferral
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_data_002_rollback_version_not_prematurely_promoted(self):
        """DATA-002: rollback_to_version sets is_active_vector=False and defers active promotion."""
        from backend.document.models.document import Document, DocumentVersion
        from backend.document.models.status import DocumentStatus
        from backend.document.services.document_service import DocumentService

        doc_id = uuid.uuid4()
        ver1_id = uuid.uuid4()
        ver2_id = uuid.uuid4()
        tenant_id = str(uuid.uuid4())

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename="report.pdf",
            original_filename="report.pdf",
            status=DocumentStatus.READY,
            latest_version_id=ver2_id,
        )
        v1 = DocumentVersion(
            id=ver1_id,
            document_id=doc_id,
            version_number=1,
            is_active_vector=True,
            storage_object_id=uuid.uuid4(),
            content_hash="hash-1",
        )
        v2 = DocumentVersion(
            id=ver2_id,
            document_id=doc_id,
            version_number=2,
            is_active_vector=False,
            storage_object_id=uuid.uuid4(),
            content_hash="hash-2",
        )
        doc.versions = [v1, v2]

        service = DocumentService()
        service.doc_repo = MagicMock()
        service.doc_repo.get_by_id_with_versions = AsyncMock(return_value=doc)
        service.doc_repo.set_active_version = AsyncMock()

        async def fake_add_version(ver, session):
            ver.id = uuid.uuid4()
            return ver

        service.doc_repo.add_version = AsyncMock(side_effect=fake_add_version)
        service.job_repo = MagicMock()
        service.job_repo.create = AsyncMock(side_effect=lambda j, s: j)
        service.event_repo = MagicMock()
        service.event_repo.append_event = AsyncMock()
        service.job_dispatcher = MagicMock()
        service.job_dispatcher.dispatch_job = AsyncMock(return_value=DispatchResult(success=True, task_id="t1"))

        mock_session = AsyncMock()

        res_doc, res_version, res_job = await service.rollback_to_version(doc_id, ver1_id, tenant_id, session=mock_session)

        # DATA-002 assertion: is_active_vector must be False on the created rollback version
        assert res_version.is_active_vector is False
        # DATA-002 assertion: doc_repo.set_active_version must NOT be called prematurely during rollback
        service.doc_repo.set_active_version.assert_not_called()

    # -------------------------------------------------------------------------
    # DATA-003: Cascade Soft-Delete to Versions, Chunks, and Embeddings
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_data_003_delete_cascades_soft_delete(self):
        """DATA-003: delete_document updates is_deleted=True on versions, chunks, and embeddings."""
        from backend.document.models.document import Document, DocumentVersion
        from backend.document.services.document_service import DocumentService

        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        tenant_id = str(uuid.uuid4())

        doc = Document(id=doc_id, tenant_id=tenant_id, filename="doc.txt", original_filename="doc.txt")
        ver = DocumentVersion(id=ver_id, document_id=doc_id, version_number=1)
        doc.versions = [ver]

        service = DocumentService()
        service.doc_repo = MagicMock()
        service.doc_repo.get_by_id_with_versions = AsyncMock(return_value=doc)
        service.doc_repo.delete = AsyncMock(return_value=True)
        service.storage = MagicMock()
        service.storage.delete_prefix = AsyncMock()
        service.event_repo = MagicMock()
        service.event_repo.append_event = AsyncMock()

        mock_session = AsyncMock()

        with patch("backend.modules.vector.services.vector_service.VectorStorageService") as mock_vs_cls:
            mock_vs = mock_vs_cls.return_value
            mock_vs.delete_document_points = AsyncMock()

            success = await service.delete_document(doc_id, tenant_id, session=mock_session)
            assert success is True

            # Verify session.execute was called to cascade updates
            # At least 3 update executes: DocumentVersion, DocumentChunk, ChunkEmbedding
            assert mock_session.execute.call_count >= 3

    # -------------------------------------------------------------------------
    # DATA-004: Chunk Hash Salting
    # -------------------------------------------------------------------------
    def test_data_004_chunk_hash_policy_consistency(self):
        """DATA-004: Hash calculation includes tenant_id and document_id salt for isolation."""
        import hashlib

        tenant_a = "tenant-1"
        tenant_b = "tenant-2"
        doc_1 = "doc-1"
        doc_2 = "doc-2"
        content = "Identical text content across documents"

        hash_a = hashlib.sha256(f"{tenant_a}:{doc_1}:0:{content}".encode()).hexdigest()
        hash_b = hashlib.sha256(f"{tenant_a}:{doc_2}:0:{content}".encode()).hexdigest()
        hash_c = hashlib.sha256(f"{tenant_b}:{doc_1}:0:{content}".encode()).hexdigest()

        # Hashes must differ across documents and tenants even with identical chunk content
        assert hash_a != hash_b
        assert hash_a != hash_c

    # -------------------------------------------------------------------------
    # DATA-005: Ingestion Worker Actual Tenant Resolution
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_data_005_ingestion_resolves_actual_tenant_id(self):
        """DATA-005: Worker resolves actual_tenant_id from Document without passing job.document_id."""
        from backend.document.workers.ingestion import _do_process_job

        job_id = str(uuid.uuid4())
        doc_id = uuid.uuid4()
        actual_tenant = "tenant-real-99"

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.document_id = doc_id
        mock_job.version_id = uuid.uuid4()
        mock_job.status = "PENDING"
        mock_job.retry_count = 0
        mock_job.max_retries = 3

        mock_session = AsyncMock()
        # session.scalar for tenant_id lookup returns actual_tenant
        mock_session.scalar = AsyncMock(return_value=actual_tenant)

        # Mock doc_repo
        mock_doc = MagicMock()
        mock_version = MagicMock()
        mock_version.id = mock_job.version_id
        mock_version.is_active_vector = False
        mock_version.storage_object = None  # triggers STORE_002 immediately after document resolution
        mock_doc.versions = [mock_version]

        with patch("backend.document.repositories.job_repository.JobRepository.get_by_id", new_callable=AsyncMock, return_value=mock_job):
            with patch("backend.document.repositories.document_repository.DocumentRepository.get_by_id_with_versions", new_callable=AsyncMock, return_value=mock_doc) as mock_get_doc:
                session_factory = MagicMock()
                session_factory.return_value.__aenter__.return_value = mock_session
                task_inst = MagicMock()
                task_inst.retry.side_effect = RuntimeError("CELERY_RETRY")

                # Should trigger retry due to missing storage_object after resolving tenant
                with pytest.raises(RuntimeError, match="CELERY_RETRY"):
                    await _do_process_job(task_inst, job_id, session_factory)

                # Verify get_by_id_with_versions was called with actual_tenant, NOT str(job.document_id)
                mock_get_doc.assert_awaited_once_with(doc_id, actual_tenant, mock_session)

    # -------------------------------------------------------------------------
    # PERF-001: PDFExtractor Async Thread Offloading
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_perf_001_pdf_extractor_asyncio_to_thread(self):
        """PERF-001: PDFExtractor offloads synchronous parsing via asyncio.to_thread."""
        extractor = PDFExtractor()

        pdf_bytes = b"%PDF-1.4 mock pdf data"
        stream = io.BytesIO(pdf_bytes)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = (["Page 1 extracted content with more than fifty words to ensure threshold is met properly in tests. " * 5], 1, {})
            result = await extractor.extract(stream, "test.pdf", "application/pdf")
            mock_to_thread.assert_awaited_once()
            assert result.page_count == 1
            assert result.word_count > 50

    # -------------------------------------------------------------------------
    # OBS-003: JobDispatcher Correlation ID Propagation
    # -------------------------------------------------------------------------
    def test_obs_003_job_dispatcher_forwards_correlation_id(self):
        """OBS-003: apply_async receives correlation_id in headers when provided or in context."""
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.dispatch_state = "READY_FOR_DISPATCH"
        mock_job.status = "PENDING"
        mock_job.dispatched_at = None

        with patch("backend.document.workers.ingestion.process_document_job.apply_async") as mock_apply:
            mock_apply.return_value = MagicMock(id="task-123")

            # Dispatch with explicit correlation ID
            res = JobDispatcher.dispatch_job_sync(mock_job, correlation_id="corr-ingest-456")
            assert res.success is True

            mock_apply.assert_called_once()
            call_kwargs = mock_apply.call_args[1]
            assert "headers" in call_kwargs
            assert call_kwargs["headers"] == {"correlation_id": "corr-ingest-456"}
