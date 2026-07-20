"""Semantic Chunk Splitter Placeholder (`semantic`).

Per Phase 2 Milestone 1 strict architectural boundaries, semantic similarity chunking
(which requires generating dense embedding vectors across sliding windows to calculate
cosine similarity drops) cannot be executed until Phase 2 Milestone 2 (`Embedding Pipeline`).
This placeholder cleanly raises ChunkStrategyNotFound (`CHK_002`) explaining the M2 dependency.
"""

from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO
from backend.modules.chunking.schemas.errors import ChunkStrategyNotFound
from .base import BaseChunkSplitter


class SemanticChunkSplitterPlaceholder(BaseChunkSplitter):
    """Architectural placeholder for embedding-based semantic splitting (`semantic`)."""

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            name="semantic",
            display_name="Semantic Similarity Splitter (Phase 2 M2 Required)",
            description="Splits text dynamically at points where dense vector cosine similarity drops across adjacent sentences. Requires Phase 2 Milestone 2 Embedding Pipeline.",
            supported_mime_types=["*"],
            default_max_characters=1000,
            default_overlap_characters=0,
            is_placeholder=True,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 0,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        raise ChunkStrategyNotFound(
            message="Semantic splitting (`semantic`) requires dense embedding vectors from the Milestone 2 Embedding Pipeline. Please select `recursive`, `markdown`, `sentence`, `paragraph`, `table`, or `code` for Milestone 1.",
            detail={"strategy": "semantic", "required_milestone": "Phase 2 Milestone 2 (Embedding Pipeline)"},
        )
