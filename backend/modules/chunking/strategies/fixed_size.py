"""Fixed Size Chunk Splitter Placeholder (`fixed_size`).

This strategy is explicitly disabled in Phase 1 (M1) as requested.
"""

from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO
from backend.modules.chunking.schemas.errors import ChunkStrategyNotFound

from .base import BaseChunkSplitter


class FixedSizeChunkSplitterPlaceholder(BaseChunkSplitter):
    """Architectural placeholder for fixed size splitting (`fixed_size`)."""

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            id="fixed_size",
            display_name="Fixed Size",
            description="Currently unavailable in Version 1.0.",
            status="disabled",
            supported_mime_types=["*"],
            default_max_characters=1000,
            default_overlap_characters=0,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 0,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        raise ChunkStrategyNotFound(
            message="Fixed size splitting is not available in RAGuard AI v1.0.",
            detail={
                "strategy": "fixed_size",
            },
        )
