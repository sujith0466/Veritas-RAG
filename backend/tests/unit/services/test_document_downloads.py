"""Unit tests for Document Original and Extracted Text Downloads (D3.5, D3.6)."""

import io
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models import Document, DocumentVersion, StorageObject, DocumentStatus

from backend.document.schemas.errors import DocumentDomainException
from backend.document.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_get_original_file_stream_success():
    """Test retrieving original file stream."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    storage_obj = StorageObject(
        id=uuid.uuid4(),
        provider="local",
        bucket_or_container="test-bucket",
        object_key="test-tenant/docs/contract.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        checksum_sha256="dummy-checksum",
    )

    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        storage_object=storage_obj,
    )
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="contract.pdf",
        original_filename="UserContract.pdf",
        latest_version_id=ver_id,
        versions=[version],
    )

    fake_stream = io.BytesIO(b"%PDF-1.4 mock content")

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc), \
         patch.object(service.storage, "object_exists", return_value=True), \
         patch.object(service.storage, "get_stream", return_value=fake_stream):

        stream, filename, mime_type, file_size = await service.get_original_file_stream(
            doc_id, "test-tenant", session
        )

        assert filename == "UserContract.pdf"
        assert mime_type == "application/pdf"
        assert file_size == 2048
        assert stream.read() == b"%PDF-1.4 mock content"


@pytest.mark.asyncio
async def test_get_extracted_text_stream_success():
    """Test retrieving normalized extracted text stream."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        extracted_text_path="test-tenant/docs/norm.txt",
    )
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="contract.pdf",
        latest_version_id=ver_id,
        versions=[version],
    )

    fake_stream = io.BytesIO(b"Normalized contract text content.")

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc), \
         patch.object(service.storage, "object_exists", return_value=True), \
         patch.object(service.storage, "get_stream", return_value=fake_stream):

        stream, filename, file_size = await service.get_extracted_text_stream(
            doc_id, "test-tenant", session
        )

        assert filename == "contract.pdf.extracted.txt"
        assert file_size == len(b"Normalized contract text content.")
        assert stream.read() == b"Normalized contract text content."


@pytest.mark.asyncio
async def test_get_extracted_text_stream_not_ready():
    """Test retrieving extracted text when not yet extracted raises domain exception."""
    service = DocumentService()
    session = AsyncMock(spec=AsyncSession)

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        extracted_text_path=None,
    )
    doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        filename="contract.pdf",
        latest_version_id=ver_id,
        versions=[version],
    )

    with patch.object(service.doc_repo, "get_by_id_with_versions", return_value=doc):
        with pytest.raises(DocumentDomainException) as exc_info:
            await service.get_extracted_text_stream(doc_id, "test-tenant", session)
        assert "not yet available" in str(exc_info.value)
