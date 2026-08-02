"""Unit tests for Document Domain DTOs & Schemas (`ADR-005`)."""

from datetime import UTC, datetime
import uuid

from backend.document.schemas.document import (
    DocumentDetailResponse,
    DocumentManifestDTO,
    DocumentResponse,
    StageMetricDTO,
)


class TestDocumentSchemas:
    """Test suite for document pydantic schemas."""

    def test_stage_metric_dto_defaults(self):
        """Verify StageMetricDTO default status and duration."""
        metric = StageMetricDTO(stage="validation", duration_ms=45.2)
        assert metric.stage == "validation"
        assert metric.duration_ms == 45.2
        assert metric.status == "COMPLETED"
        assert metric.error_message is None

    def test_document_manifest_dto_creation(self):
        """Verify canonical DocumentManifestDTO instantiation and defaults (`Refinement 1`)."""
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        manifest = DocumentManifestDTO(
            manifest_version="1.0.0",
            document_id=doc_id,
            version_id=ver_id,
            version_number=1,
            tenant_id="tenant-acme",
            owner_user_id=None,
            filename="contract.pdf",
            original_filename="contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=1048576,
            checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            storage_provider="local_volume",
            original_storage_key=f"tenant-acme/{doc_id}/{ver_id}/original/contract.pdf",
            page_count=12,
            word_count=3400,
            language="en",
            created_at=datetime.now(UTC).isoformat(),
        )
        assert manifest.manifest_version == "1.0.0"
        assert manifest.document_id == doc_id
        assert manifest.checksum_sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert manifest.stage_metrics == []
        assert manifest.extraction_metadata == {}

    def test_document_response_and_detail_response(self):
        """Verify DocumentResponse and DocumentDetailResponse structures."""
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        now = datetime.now(UTC)

        response = DocumentResponse(
            id=doc_id,
            tenant_id="tenant-acme",
            filename="spec.docx",
            original_filename="spec.docx",
            status="PROCESSED",
            latest_version_id=ver_id,
            word_count=1500,
            page_count=5,
            language="en",
            created_at=now,
            updated_at=now,
        )
        assert response.id == doc_id
        assert response.status == "PROCESSED"

        detail = DocumentDetailResponse(
            id=doc_id,
            tenant_id="tenant-acme",
            filename="spec.docx",
            original_filename="spec.docx",
            status="PROCESSED",
            latest_version_id=ver_id,
            word_count=1500,
            page_count=5,
            language="en",
            created_at=now,
            updated_at=now,
            versions=[],
            manifest=None,
        )
        assert detail.versions == []
        assert detail.manifest is None
