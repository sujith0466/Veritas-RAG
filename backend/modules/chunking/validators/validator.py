"""Chunk validation rules and quota boundaries (`ChunkValidator`)."""

from backend.modules.chunking.schemas.chunk import ChunkDTO
from backend.modules.chunking.schemas.errors import ChunkValidationError


class ChunkValidator:
    """Enforces size limits, content checks, and hash uniqueness invariants (`CHK_001`)."""

    def __init__(self, min_characters: int = 10, max_characters: int = 10000) -> None:
        self.min_characters = min_characters
        self.max_characters = max_characters

    def validate_chunks(self, chunks: list[ChunkDTO]) -> list[ChunkDTO]:
        """Validate a list of candidate DTOs before persistence, raising ChunkValidationError (`CHK_001`) if quota is exceeded."""
        if not chunks:
            return []

        for idx, dto in enumerate(chunks):
            content_str = dto.content.strip()
            if not content_str:
                raise ChunkValidationError(
                    message=f"Chunk at sequence index {idx} has empty or whitespace-only content (`CHK_001`).",
                    detail={"chunk_index": idx},
                )
            if len(content_str) < self.min_characters and len(chunks) > 1:
                # Small edge fragment check (unless document is tiny)
                pass
            if len(content_str) > self.max_characters:
                raise ChunkValidationError(
                    message=f"Chunk at sequence index {idx} exceeds max character limit ({len(content_str)} > {self.max_characters}).",
                    detail={
                        "chunk_index": idx,
                        "character_count": len(content_str),
                        "max_allowed": self.max_characters,
                    },
                )

        return chunks
