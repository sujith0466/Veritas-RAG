"""Unit tests for Document State Taxonomy & Contract Verification (`Phase D3.7`)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.document.models.status import DocumentStatus
from backend.document.schemas.status import ProcessingStatusResponse
from backend.document.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_document_status_all_enum_values_mapped_in_service():
    """Verify all DocumentStatus enum values have deterministic progress mappings."""
    service = DocumentService()
    doc_id = uuid.uuid4()
    tenant_id = "test-tenant"

    for status_val in DocumentStatus:
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.status = status_val.value
        mock_doc.updated_at = "2026-10-02T10:00:00Z"

        mock_session = AsyncMock()
        with patch.object(service.doc_repo, "get_by_id", return_value=mock_doc), \
             patch.object(service.job_repo, "get_by_document_id", return_value=None):
            resp = await service.get_status(doc_id, tenant_id, mock_session)
            assert resp is not None
            assert resp.status == status_val.value
            assert 0 <= resp.progress_percent <= 100


@pytest.mark.asyncio
async def test_document_status_monotonic_progress_ordering():
    """Verify pipeline stages progress monotonically from UPLOADED (10%) to READY (100%)."""
    service = DocumentService()
    doc_id = uuid.uuid4()
    tenant_id = "test-tenant"

    ordered_pipeline = [
        DocumentStatus.UPLOADED.value,
        DocumentStatus.VALIDATING.value,
        DocumentStatus.EXTRACTING.value,
        DocumentStatus.OCR.value,
        DocumentStatus.MANIFEST_GENERATING.value,
        DocumentStatus.PROCESSED.value,
        DocumentStatus.CHUNKING.value,
        DocumentStatus.EMBEDDING.value,
        DocumentStatus.VECTOR_SYNC.value,
        DocumentStatus.READY.value,
    ]

    previous_progress = 0
    for stage_status in ordered_pipeline:
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.status = stage_status
        mock_doc.updated_at = "2026-10-02T10:00:00Z"

        mock_session = AsyncMock()
        with patch.object(service.doc_repo, "get_by_id", return_value=mock_doc), \
             patch.object(service.job_repo, "get_by_document_id", return_value=None):
            resp = await service.get_status(doc_id, tenant_id, mock_session)
            assert resp.progress_percent > previous_progress, f"{stage_status} ({resp.progress_percent}%) should be > previous ({previous_progress}%)"
            previous_progress = resp.progress_percent

    assert previous_progress == 100  # READY is 100%


@pytest.mark.asyncio
async def test_processing_status_response_schema_compatibility():
    """Verify ProcessingStatusResponse can serialize all canonical statuses."""
    for status_val in DocumentStatus:
        resp = ProcessingStatusResponse(
            document_id=uuid.uuid4(),
            status=status_val.value,
            current_step="test_step",
            progress_percent=50,
            retry_count=0,
            error_code=None,
            error_message=None,
            updated_at="2026-10-02T10:00:00Z",
        )
        assert resp.status == status_val.value
