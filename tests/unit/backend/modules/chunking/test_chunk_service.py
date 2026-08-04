"""Unit tests for ChunkingService (`ADR-005`)."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.document.models import Document, DocumentVersion
from backend.modules.chunking.schemas.errors import ChunkNotFoundException
from backend.modules.chunking.services.chunk_service import ChunkingService


@pytest.mark.asyncio
class TestChunkingService:
    """Test suite verifying orchestration logic in ChunkingService."""

    async def test_chunk_document_version_success(self) -> None:
        tenant_id = "test_tenant"
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        doc_mock = Document(id=doc_id, tenant_id=tenant_id, filename="test.md", status="PROCESSED")
        ver_mock = DocumentVersion(
            id=ver_id,
            document_id=doc_id,
            version_number=1,
            extracted_text_path="tenant/doc/ver/text.txt",
            metadata_json={"mime_type": "text/markdown"},
        )

        mock_session = AsyncMock()
        # Mock execute returning doc, then version, then delete result, then count
        result_doc = MagicMock()
        result_doc.scalar_one_or_none.return_value = doc_mock

        result_ver = MagicMock()
        result_ver.scalar_one_or_none.return_value = ver_mock

        result_del = MagicMock()
        result_del.rowcount = 0

        mock_session.execute.side_effect = [
            result_doc, 
            result_ver, 
            result_del,
            result_doc,
            result_doc,
            result_doc
        ]

        # Mock storage provider
        mock_storage = AsyncMock()
        mock_storage.object_exists.return_value = True
        mock_storage.get_bytes.return_value = (
            b"# Heading 1\nSome paragraph under heading 1.\n## Heading 1.1\nAnother paragraph right here."
        )

        service = ChunkingService(storage_provider=mock_storage)
        chunks, duration_ms = await service.chunk_document_version(
            tenant_id=tenant_id,
            document_id=doc_id,
            version_id=ver_id,
            session=mock_session,
            strategy_override=None,  # Auto-resolve from MIME to markdown
            max_characters=500,
            overlap_characters=50,
        )

        assert len(chunks) == 2
        assert chunks[0].strategy_used == "markdown"
        assert chunks[0].previous_chunk_id is None
        assert chunks[0].next_chunk_id == chunks[1].id
        assert chunks[1].previous_chunk_id == chunks[0].id
        assert chunks[1].next_chunk_id is None

        # Verify no embedding generated
        assert all(c.is_embedded is False for c in chunks)
        assert doc_mock.status == "CHUNKED"
        assert duration_ms >= 0.0

    async def test_chunk_document_version_missing_doc_raises_chk_005(self) -> None:
        mock_session = AsyncMock()
        result_doc = MagicMock()
        result_doc.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_doc

        service = ChunkingService()
        with pytest.raises(ChunkNotFoundException) as exc_info:
            await service.chunk_document_version("t1", uuid.uuid4(), uuid.uuid4(), mock_session)
        assert exc_info.value.code == "CHK_005"
