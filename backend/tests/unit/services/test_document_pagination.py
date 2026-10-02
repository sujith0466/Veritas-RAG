"""Unit tests for Document Pagination, Search, and Sorting (`Phase D3.3`)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.document.repositories.document_repository import DocumentRepository
from backend.document.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_document_service_list_documents_pagination_and_search():
    """Verify DocumentService.list_documents correctly passes pagination, search, and sort parameters."""
    service = DocumentService()
    tenant_id = "test-tenant-123"

    mock_doc = MagicMock()
    mock_doc.id = uuid.uuid4()
    mock_doc.tenant_id = tenant_id
    mock_doc.filename = "report_q3.pdf"
    mock_doc.original_filename = "original_report.pdf"
    mock_doc.status = "READY"
    mock_doc.word_count = 1200
    mock_doc.page_count = 4
    mock_doc.language = "en"
    mock_doc.created_at = "2026-10-02T10:00:00Z"
    mock_doc.updated_at = "2026-10-02T10:05:00Z"
    mock_doc.latest_version_id = uuid.uuid4()
    mock_doc.owner_user_id = None
    mock_doc.user_metadata = {}
    mock_doc.relative_path = None

    mock_session = AsyncMock()

    with patch.object(
        service.doc_repo,
        "list_documents",
        return_value=([mock_doc], 45)
    ) as mock_list:
        resp = await service.list_documents(
            tenant_id=tenant_id,
            session=mock_session,
            page=2,
            page_size=20,
            status="READY",
            search="report",
            sort_by="filename",
            sort_order="asc",
        )

        mock_list.assert_called_once_with(
            tenant_id=tenant_id,
            session=mock_session,
            page=2,
            page_size=20,
            status="READY",
            search="report",
            sort_by="filename",
            sort_order="asc",
        )

        assert resp.total == 45
        assert resp.page == 2
        assert resp.page_size == 20
        assert resp.pages == 3  # math.ceil(45 / 20) = 3
        assert len(resp.items) == 1
        assert resp.items[0].filename == "report_q3.pdf"
