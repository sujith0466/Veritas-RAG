"""Unit tests for Document Processing Contract (`Refinement 6`)."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.document.models import Document, DocumentVersion
from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode
from backend.document.storage.contract import DocumentProcessingContract


@pytest.mark.asyncio
class TestDocumentProcessingContract:
    """Test suite verifying contract invariant checks before marking a document processed."""

    async def test_verify_contract_success(self):
        """Verify contract passes when all required entities and storage artifacts exist (`Refinement 6`)."""
        doc = MagicMock(spec=Document)
        doc.id = uuid.uuid4()
        doc.tenant_id = "tenant-1"

        storage_obj = MagicMock()
        storage_obj.object_key = "documents/tenant-1/doc/v1/original/test.pdf"

        ver = MagicMock(spec=DocumentVersion)
        ver.id = uuid.uuid4()
        ver.version_number = 1
        ver.storage_object_id = uuid.uuid4()
        ver.storage_object = storage_obj
        ver.extracted_text_path = "documents/tenant-1/doc/v1/normalized/text.txt"

        storage_provider = AsyncMock()
        storage_provider.object_exists.return_value = True

        result = await DocumentProcessingContract.verify(doc, ver, storage_provider)
        assert result is True
        assert storage_provider.object_exists.call_count == 3

    async def test_verify_contract_missing_normalized_text(self):
        """Verify contract raises DocumentDomainException(CONTRACT_001) if normalized text is missing (`Refinement 6`)."""
        doc = MagicMock(spec=Document)
        doc.id = uuid.uuid4()
        doc.tenant_id = "tenant-1"

        storage_obj = MagicMock()
        storage_obj.object_key = "documents/tenant-1/doc/v1/original/test.pdf"

        ver = MagicMock(spec=DocumentVersion)
        ver.id = uuid.uuid4()
        ver.version_number = 1
        ver.storage_object_id = uuid.uuid4()
        ver.storage_object = storage_obj
        ver.extracted_text_path = "documents/tenant-1/doc/v1/normalized/text.txt"

        storage_provider = AsyncMock()
        # Original exists, but normalized text does NOT exist
        storage_provider.object_exists.side_effect = [True, False, True]

        with pytest.raises(DocumentDomainException) as exc_info:
            await DocumentProcessingContract.verify(doc, ver, storage_provider)

        assert exc_info.value.error_code == "CONTRACT_001"
        assert "Normalized text artifact (`text.txt`) missing" in str(exc_info.value)
