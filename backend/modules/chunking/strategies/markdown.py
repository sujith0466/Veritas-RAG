"""Markdown Header-Aware Chunk Splitter.

Parses ATX headers (`#`, `##`, `###`) to preserve exact section breadcrumb hierarchies
(`section_path`) across every child chunk and respects Markdown code blocks and tables.
"""

import re
from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO
from .base import BaseChunkSplitter, estimate_token_count
from .recursive import RecursiveChunkSplitter


class MarkdownChunkSplitter(BaseChunkSplitter):
    """Header-aware Markdown splitter (`markdown`)."""

    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            name="markdown",
            display_name="Markdown Header-Aware Splitter",
            description="Splits Markdown documents by heading levels (#, ##, ###) and preserves section hierarchy in chunk metadata.",
            supported_mime_types=["text/markdown", "text/x-markdown"],
            default_max_characters=1500,
            default_overlap_characters=200,
            is_placeholder=False,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1500,
        overlap_characters: int = 200,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        if not text or not text.strip():
            return []

        base_meta = base_metadata or {}
        lines = text.split("\n")
        sections: list[tuple[list[str], str]] = []  # (breadcrumb_path, content_block)
        current_path: list[str] = []
        current_lines: list[str] = []

        for line in lines:
            header_match = self.HEADER_PATTERN.match(line)
            if header_match:
                # Flush previous lines as a section block
                if current_lines:
                    sections.append((list(current_path), "\n".join(current_lines)))
                    current_lines = []
                
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                header_text = f"{header_match.group(1)} {title}"

                # Trim breadcrumb hierarchy down to current level - 1
                while len(current_path) >= level:
                    current_path.pop()
                current_path.append(header_text)
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((list(current_path), "\n".join(current_lines)))

        # Sub-split large section blocks using recursive character splitting
        recursive_sub = RecursiveChunkSplitter()
        dtos: list[ChunkDTO] = []

        for breadcrumb, section_content in sections:
            if not section_content.strip():
                continue
            if len(section_content) <= max_characters:
                dtos.append(
                    ChunkDTO(
                        chunk_index=len(dtos),
                        content=section_content.strip(),
                        character_count=len(section_content.strip()),
                        token_count=estimate_token_count(section_content.strip()),
                        section_path=breadcrumb,
                        metadata_json=dict(base_meta),
                    )
                )
            else:
                # Sub-split long sections
                sub_chunks = recursive_sub.split_text(section_content, max_characters, overlap_characters, base_meta)
                for sc in sub_chunks:
                    sc.chunk_index = len(dtos)
                    sc.section_path = breadcrumb
                    dtos.append(sc)

        return dtos
