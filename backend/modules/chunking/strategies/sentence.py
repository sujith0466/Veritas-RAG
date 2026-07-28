"""Sentence & Paragraph Chunk Splitters.

SentenceChunkSplitter groups complete sentences using NLP/punctuation boundary detection up to size quota.
ParagraphChunkSplitter splits cleanly on double-newlines (`\n\n`) to keep prose blocks intact.
"""

import re
from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO

from .base import BaseChunkSplitter, estimate_token_count
from .recursive import _merge_splits


class SentenceChunkSplitter(BaseChunkSplitter):
    """Sentence boundary preserving splitter (`sentence`)."""

    SENTENCE_END_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            id="sentence",
            display_name="Sentence Boundaries",
            description="Splits text at sentence boundaries for fine-grained chunking.",
            status="supported",
            supported_mime_types=["text/plain", "*"],
            default_max_characters=800,
            default_overlap_characters=100,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 150,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        if not text or not text.strip():
            return []

        base_meta = base_metadata or {}
        # Split into sentence candidates
        sentences = self.SENTENCE_END_PATTERN.split(text)
        merged = _merge_splits(
            sentences,
            separator=" ",
            chunk_size=max_characters,
            chunk_overlap=overlap_characters,
        )

        dtos: list[ChunkDTO] = []
        for chunk_text in merged:
            cleaned = chunk_text.strip()
            if not cleaned:
                continue
            dtos.append(
                ChunkDTO(
                    chunk_index=len(dtos),
                    content=cleaned,
                    character_count=len(cleaned),
                    token_count=estimate_token_count(cleaned),
                    metadata_json=dict(base_meta),
                )
            )
        return dtos


class ParagraphChunkSplitter(BaseChunkSplitter):
    """Paragraph double-newline block splitter (`paragraph`)."""

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            id="paragraph",
            display_name="Paragraph Boundaries",
            description="Splits text strictly at paragraph boundaries to ensure natural reading chunks.",
            status="supported",
            supported_mime_types=["text/plain", "*"],
            default_max_characters=1500,
            default_overlap_characters=0,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1200,
        overlap_characters: int = 200,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        if not text or not text.strip():
            return []

        base_meta = base_metadata or {}
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        merged = _merge_splits(
            paragraphs,
            separator="\n\n",
            chunk_size=max_characters,
            chunk_overlap=overlap_characters,
        )

        dtos: list[ChunkDTO] = []
        for chunk_text in merged:
            cleaned = chunk_text.strip()
            if not cleaned:
                continue
            dtos.append(
                ChunkDTO(
                    chunk_index=len(dtos),
                    content=cleaned,
                    character_count=len(cleaned),
                    token_count=estimate_token_count(cleaned),
                    metadata_json=dict(base_meta),
                )
            )
        return dtos
