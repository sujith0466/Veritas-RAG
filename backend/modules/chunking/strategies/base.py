"""Abstract base class for all document chunking splitters."""

import math
from abc import ABC, abstractmethod
from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO


def estimate_token_count(text: str) -> int:
    """Estimate token count using 4 characters per token heuristic for fast synchronous processing."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4.0))


class BaseChunkSplitter(ABC):
    """Abstract interface for content-aware chunk splitters (`ADR-005`)."""

    @property
    @abstractmethod
    def strategy_info(self) -> StrategyInfoDTO:
        """Return canonical strategy metadata including display name and supported MIME types."""
        ...

    @abstractmethod
    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 200,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        """Split normalized text into structured ChunkDTO instances with sequence order and token gauges."""
        ...

    def supports_mime(self, mime_type: str) -> bool:
        """Check whether this splitter is designed to process the given MIME type."""
        info = self.strategy_info
        if "*" in info.supported_mime_types:
            return True
        return any(
            mime_type.lower().startswith(supported.lower())
            for supported in info.supported_mime_types
        )
