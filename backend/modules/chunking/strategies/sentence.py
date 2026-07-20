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
            name="sentence",
            display_name="Sentence Boundary Splitter",
            description="Splits text along grammatical sentence boundaries, combining consecutive sentences up to target character length.",
            supported_mime_types=["*"],
            default_max_characters=1000,
            default_overlap_characters=150,
            is_placeholder=False,
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
        merged = _merge_splits(sentences, separator=" ", chunk_size=max_characters, chunk_overlap=overlap_characters)

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
            name="paragraph",
            display_name="Paragraph Block Splitter",
            description="Splits strictly on double newline boundaries (`\\n\\n`), preserving paragraph blocks and merging small paragraphs.",
            supported_mime_types=["*"],
            default_max_characters=1200,
            default_overlap_characters=200,
            is_placeholder=False,
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
        merged = _merge_splits(paragraphs, separator="\n\n", chunk_size=max_characters, chunk_overlap=overlap_characters)

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
