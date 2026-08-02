"""Unit tests for ChunkValidator and ChunkProcessingContract (`ADR-005`)."""

import uuid

import pytest

from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.chunking.schemas.chunk import ChunkDTO
from backend.modules.chunking.schemas.errors import (
    ChunkContractViolationError,
    ChunkValidationError,
)
from backend.modules.chunking.validators import ChunkProcessingContract, ChunkValidator


class TestValidatorsAndContract:
    """Test suite verifying validation boundaries and doubly-linked graph contract check."""

    def test_chunk_validator_valid_chunks(self) -> None:
        validator = ChunkValidator(min_characters=10, max_characters=100)
        dtos = [
            ChunkDTO(chunk_index=0, content="This is a valid chunk that meets limits."),
            ChunkDTO(chunk_index=1, content="Another valid chunk string for testing."),
        ]
        validated = validator.validate_chunks(dtos)
        assert len(validated) == 2

    def test_chunk_validator_empty_chunk_raises_chk_001(self) -> None:
        validator = ChunkValidator()
        dtos = [
            ChunkDTO(chunk_index=0, content="Valid first chunk content."),
            ChunkDTO(chunk_index=1, content="   \n\t  "),  # Whitespace only
        ]
        with pytest.raises(ChunkValidationError) as exc_info:
            validator.validate_chunks(dtos)
        assert exc_info.value.code == "CHK_001"
        assert "empty or whitespace-only" in exc_info.value.message

    def test_chunk_validator_exceeds_max_raises_chk_001(self) -> None:
        validator = ChunkValidator(max_characters=50)
        dtos = [
            ChunkDTO(chunk_index=0, content="A" * 60),
        ]
        with pytest.raises(ChunkValidationError) as exc_info:
            validator.validate_chunks(dtos)
        assert exc_info.value.code == "CHK_001"
        assert "exceeds max character limit" in exc_info.value.message

    def test_chunk_processing_contract_verify_success(self) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        id_0 = uuid.uuid4()
        id_1 = uuid.uuid4()
        id_2 = uuid.uuid4()

        chunks = [
            DocumentChunk(
                id=id_0,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=0,
                content="Chunk zero",
                content_hash="hash0",
                strategy_used="recursive",
                previous_chunk_id=None,
                next_chunk_id=id_1,
            ),
            DocumentChunk(
                id=id_1,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=1,
                content="Chunk one",
                content_hash="hash1",
                strategy_used="recursive",
                previous_chunk_id=id_0,
                next_chunk_id=id_2,
            ),
            DocumentChunk(
                id=id_2,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=2,
                content="Chunk two",
                content_hash="hash2",
                strategy_used="recursive",
                previous_chunk_id=id_1,
                next_chunk_id=None,
            ),
        ]

        assert ChunkProcessingContract.verify(chunks) is True

    def test_chunk_processing_contract_verify_zero_chunks_raises_chk_004(self) -> None:
        with pytest.raises(ChunkContractViolationError) as exc_info:
            ChunkProcessingContract.verify([])
        assert exc_info.value.code == "CHK_004"
        assert "Zero chunks generated" in exc_info.value.message

    def test_chunk_processing_contract_verify_broken_prev_link_raises_chk_004(self) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        id_0 = uuid.uuid4()
        id_1 = uuid.uuid4()

        chunks = [
            DocumentChunk(
                id=id_0,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=0,
                content="Chunk 0",
                content_hash="h0",
                strategy_used="recursive",
                previous_chunk_id=None,
                next_chunk_id=id_1,
            ),
            DocumentChunk(
                id=id_1,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=1,
                content="Chunk 1",
                content_hash="h1",
                strategy_used="recursive",
                previous_chunk_id=uuid.uuid4(),  # Broken pointer to non-existent ID!
                next_chunk_id=None,
            ),
        ]

        with pytest.raises(ChunkContractViolationError) as exc_info:
            ChunkProcessingContract.verify(chunks)
        assert exc_info.value.code == "CHK_004"
        assert "Broken doubly-linked `previous_chunk_id` pointer" in exc_info.value.message

    def test_chunk_processing_contract_verify_broken_next_link_raises_chk_004(self) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        id_0 = uuid.uuid4()
        id_1 = uuid.uuid4()

        chunks = [
            DocumentChunk(
                id=id_0,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=0,
                content="Chunk 0",
                content_hash="h0",
                strategy_used="recursive",
                previous_chunk_id=None,
                next_chunk_id=None,  # Broken pointer! Must point to id_1
            ),
            DocumentChunk(
                id=id_1,
                tenant_id="test_tenant",
                document_id=doc_id,
                document_version_id=ver_id,
                chunk_index=1,
                content="Chunk 1",
                content_hash="h1",
                strategy_used="recursive",
                previous_chunk_id=id_0,
                next_chunk_id=None,
            ),
        ]

        with pytest.raises(ChunkContractViolationError) as exc_info:
            ChunkProcessingContract.verify(chunks)
        assert exc_info.value.code == "CHK_004"
        assert "Broken doubly-linked `next_chunk_id` pointer" in exc_info.value.message
