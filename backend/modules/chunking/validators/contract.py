"""Chunk Processing Contract verification (`CHK_004`).

Strictly verifies that when a document version is chunked, at least one valid chunk exists
in `document_chunks` and that doubly-linked sequential chain pointers (`prev` <-> `next`)
are intact before transitioning status.
"""

from typing import Sequence

from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.chunking.schemas.errors import ChunkContractViolationError


class ChunkProcessingContract:
    """Enforces absolute completeness of chunking persistence and graph linking."""

    @classmethod
    def verify(cls, chunks: Sequence[DocumentChunk]) -> bool:
        """Verify chunk processing completeness and doubly-linked graph invariants (`CHK_004`).

        Raises ChunkContractViolationError (`CHK_004`) if invariants are broken.
        """
        if not chunks:
            raise ChunkContractViolationError(
                message="Contract failure: Zero chunks generated or persisted for document version (`CHK_004`).",
            )

        # Sort by chunk_index to verify sequential consistency
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)

        for i, chunk in enumerate(sorted_chunks):
            if chunk.chunk_index != i:
                raise ChunkContractViolationError(
                    message=f"Contract failure: Chunk sequence index gap at index {i} (`CHK_004`).",
                    detail={"expected_index": i, "actual_index": chunk.chunk_index, "chunk_id": str(chunk.id)},
                )

            # Verify previous pointer
            if i > 0:
                prev_expected = sorted_chunks[i - 1].id
                if chunk.previous_chunk_id != prev_expected:
                    raise ChunkContractViolationError(
                        message=f"Contract failure: Broken doubly-linked `previous_chunk_id` pointer at index {i}.",
                        detail={"chunk_id": str(chunk.id), "expected_prev": str(prev_expected), "actual_prev": str(chunk.previous_chunk_id)},
                    )
            else:
                if chunk.previous_chunk_id is not None:
                    raise ChunkContractViolationError(
                        message="Contract failure: First chunk (index 0) must have null `previous_chunk_id`.",
                        detail={"chunk_id": str(chunk.id)},
                    )

            # Verify next pointer
            if i < len(sorted_chunks) - 1:
                next_expected = sorted_chunks[i + 1].id
                if chunk.next_chunk_id != next_expected:
                    raise ChunkContractViolationError(
                        message=f"Contract failure: Broken doubly-linked `next_chunk_id` pointer at index {i}.",
                        detail={"chunk_id": str(chunk.id), "expected_next": str(next_expected), "actual_next": str(chunk.next_chunk_id)},
                    )
            else:
                if chunk.next_chunk_id is not None:
                    raise ChunkContractViolationError(
                        message="Contract failure: Last chunk must have null `next_chunk_id`.",
                        detail={"chunk_id": str(chunk.id)},
                    )

        return True
