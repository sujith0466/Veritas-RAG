"""Unit tests for DocumentReconciliationService (Phase D2.6)."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus
from backend.document.services.reconciliation import (
    DocumentReconciliationService,
    ReconciliationReport,
)
from backend.modules.chunking.models.chunk import DocumentChunk


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_reconciliation_scan_classifications(mock_session):
    """Test reconciliation classifies Healthy Ready, Class A, Class B, and Class C."""
    tenant_id = "test-tenant-123"

    doc_ready = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        filename="ready.txt",
    )
    doc_class_a = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=DocumentStatus.UPLOADED,
        filename="class_a.txt",
    )
    doc_class_b = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=DocumentStatus.UPLOADED,
        filename="class_b.txt",
    )
    doc_class_c = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=DocumentStatus.FAILED,
        filename="class_c.pdf",
    )

    # 1. Mock document query returning 4 documents
    mock_docs_res = MagicMock()
    mock_docs_res.scalars.return_value.all.return_value = [
        doc_ready,
        doc_class_a,
        doc_class_b,
        doc_class_c,
    ]

    # Preflight mocks
    valid_preflight = MagicMock(is_valid=True, anomaly_type=None)
    missing_preflight = MagicMock(is_valid=False, anomaly_type="HISTORICAL_WINDOWS_PATH")

    def preflight_side_effect(storage_obj, expected_tenant_id):
        if storage_obj.object_key == "key-class-a":
            return valid_preflight
        elif storage_obj.object_key == "key-ready":
            return valid_preflight
        return missing_preflight

    # Setup execute returns for version, chunk count, emb count, vec count, job
    async def mock_execute(stmt):
        stmt_str = str(stmt)
        params = stmt.compile().params if hasattr(stmt, "compile") else {}
        param_vals = list(params.values())
        res = MagicMock()
        if "FROM documents" in stmt_str:
            return mock_docs_res
        elif "FROM document_versions" in stmt_str:
            ver = MagicMock()
            ver.storage_object = MagicMock()
            if doc_class_a.id in param_vals:
                ver.storage_object.object_key = "key-class-a"
            elif doc_ready.id in param_vals:
                ver.storage_object.object_key = "key-ready"
            else:
                ver.storage_object.object_key = "key-class-b"
            res.scalar_one_or_none.return_value = ver
            return res
        elif "count(document_chunks.id)" in stmt_str:
            res.scalar.return_value = 2 if doc_ready.id in param_vals else 0
            return res
        elif "count(chunk_embeddings.id)" in stmt_str:
            res.scalar.return_value = 2 if doc_ready.id in param_vals else 0
            return res
        elif "count(vector_index_metadata.id)" in stmt_str:
            res.scalar.return_value = 2 if doc_ready.id in param_vals else 0
            return res
        elif "FROM processing_jobs" in stmt_str:
            job = MagicMock(status="COMPLETED", dispatch_state="ACKNOWLEDGED")
            res.scalar_one_or_none.return_value = job
            return res
        return res

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    with patch("backend.document.storage.preflight.StoragePreflightValidator.validate", side_effect=preflight_side_effect):
        report = await DocumentReconciliationService.scan_tenant(
            tenant_id=tenant_id,
            session=mock_session,
            dry_run=True,
        )

        assert report.dry_run is True
        assert report.total_documents == 4
        assert report.healthy_count == 1
        assert report.class_a_count == 1
        assert report.class_b_count == 1
        assert report.class_c_count == 1

        # Verify markdown output can be generated
        md = report.to_markdown()
        assert "# Document Pipeline Reconciliation Report" in md
        assert tenant_id in md
        assert "HEALTHY_READY" in md
        assert "CLASS_A_STRANDED_WITH_STORAGE" in md
        assert "CLASS_B_STRANDED_MISSING_STORAGE" in md

        # Verify json output
        d = report.to_dict()
        assert d["total_documents"] == 4
        assert d["summary"]["healthy_ready"] == 1
        assert d["summary"]["class_a_intact_storage"] == 1
        assert d["summary"]["class_b_missing_storage"] == 1
        assert d["summary"]["class_c_failed"] == 1


@pytest.mark.asyncio
async def test_reconciliation_parity_drift(mock_session):
    """Test reconciliation detects READY documents with chunk vs vector parity drift."""
    tenant_id = "test-tenant-drift"

    doc_drift = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        filename="drift.txt",
    )

    mock_docs_res = MagicMock()
    mock_docs_res.scalars.return_value.all.return_value = [doc_drift]

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        res = MagicMock()
        if "FROM documents" in stmt_str:
            return mock_docs_res
        elif "FROM document_versions" in stmt_str:
            ver = MagicMock()
            ver.storage_object = MagicMock(object_key="key-drift")
            res.scalar_one_or_none.return_value = ver
            return res
        elif "count(document_chunks.id)" in stmt_str:
            res.scalar.return_value = 10  # 10 chunks in PG
            return res
        elif "count(chunk_embeddings.id)" in stmt_str:
            res.scalar.return_value = 10
            return res
        elif "count(vector_index_metadata.id)" in stmt_str:
            res.scalar.return_value = 2   # Only 2 vectors in Qdrant! (drift)
            return res
        elif "FROM processing_jobs" in stmt_str:
            res.scalar_one_or_none.return_value = None
            return res
        return res

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    with patch("backend.document.storage.preflight.StoragePreflightValidator.validate", return_value=MagicMock(is_valid=True, anomaly_type=None)):
        report = await DocumentReconciliationService.scan_tenant(
            tenant_id=tenant_id,
            session=mock_session,
            dry_run=True,
        )

        assert report.other_discrepancy_count == 1
        assert report.items[0].classification == "READY_PARITY_DRIFT"
        assert report.items[0].chunk_count == 10
        assert report.items[0].vector_count == 2

