"""Sliding Window Chunk Splitter (`sliding_window`).

Chunks text using a fixed-size sliding window with character overlap.
"""

from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO

from .base import BaseChunkSplitter


class SlidingWindowChunkSplitter(BaseChunkSplitter):
    """Fixed-size sliding window with character overlap."""

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            id="sliding_window",
            display_name="Sliding Window",
            description="Fixed-size window with overlap.",
            status="stable",
            requires=[],
            supported_mime_types=["*"],
            default_max_characters=1000,
            default_overlap_characters=200,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 200,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        if not text:
            return []

        chunks = []
        step_size = max(1, max_characters - overlap_characters)
        idx = 0

        for i in range(0, len(text), step_size):
            chunk_text = text[i:i + max_characters]
            metadata = dict(base_metadata) if base_metadata else {}
            metadata["chunk_index"] = idx

            chunks.append(
                ChunkDTO(
                    sequence_number=idx + 1,
                    content=chunk_text,
                    byte_size=len(chunk_text.encode("utf-8")),
                    token_count=len(chunk_text) // 4,
                    metadata=metadata,
                )
            )
            idx += 1

        return chunks
