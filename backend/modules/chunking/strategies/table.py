"""Table & Code Chunk Splitters.

TableChunkSplitter parses Markdown/CSV tables and ensures every chunked row or row group
retains the header row (`<th>` prefix) so vector retrieval preserves exact schema columns.
CodeChunkSplitter detects language structure (`def`, `class`, `function`, braces) to split
code files without breaking syntax structures.
"""

from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO

from .base import BaseChunkSplitter, estimate_token_count
from .recursive import RecursiveChunkSplitter


class TableChunkSplitter(BaseChunkSplitter):
    """Table schema preserving splitter (`table`)."""

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            name="table",
            display_name="Table Schema Preserving Splitter",
            description="Parses tables (CSV or Markdown) and prefixes every split row group with column header titles for context fidelity.",
            supported_mime_types=[
                "text/csv",
                "application/csv",
                "text/tab-separated-values",
            ],
            default_max_characters=1000,
            default_overlap_characters=100,
            is_placeholder=False,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 100,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        if not text or not text.strip():
            return []

        base_meta = base_metadata or {}
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            return []

        # Check if Markdown table format (| col1 | col2 |)
        if lines[0].startswith("|") and len(lines) >= 2 and "|" in lines[1]:
            header_row = lines[0]
            divider_row = lines[1]
            data_rows = lines[2:]
            header_prefix = f"{header_row}\n{divider_row}\n"
        else:
            # Assume CSV or plain header
            header_row = lines[0]
            data_rows = lines[1:]
            header_prefix = f"{header_row}\n"

        dtos: list[ChunkDTO] = []
        current_rows: list[str] = []
        current_len = len(header_prefix)

        for row in data_rows:
            if current_rows and (current_len + len(row) + 1 > max_characters):
                chunk_content = header_prefix + "\n".join(current_rows)
                dtos.append(
                    ChunkDTO(
                        chunk_index=len(dtos),
                        content=chunk_content.strip(),
                        character_count=len(chunk_content.strip()),
                        token_count=estimate_token_count(chunk_content.strip()),
                        metadata_json={
                            **base_meta,
                            "has_table_headers": True,
                            "header_row": header_row,
                        },
                    )
                )
                current_rows = []
                current_len = len(header_prefix)
            current_rows.append(row)
            current_len += len(row) + 1

        if current_rows:
            chunk_content = header_prefix + "\n".join(current_rows)
            dtos.append(
                ChunkDTO(
                    chunk_index=len(dtos),
                    content=chunk_content.strip(),
                    character_count=len(chunk_content.strip()),
                    token_count=estimate_token_count(chunk_content.strip()),
                    metadata_json={
                        **base_meta,
                        "has_table_headers": True,
                        "header_row": header_row,
                    },
                )
            )

        return dtos


class CodeChunkSplitter(BaseChunkSplitter):
    """AST/Syntax definition boundary respecting splitter (`code`)."""

    BLOCK_SEPARATORS = [
        "\nclass ",
        "\ndef ",
        "\nasync def ",
        "\nfunction ",
        "\nexport class ",
        "\nexport function ",
        "\n// ",
        "\n# ",
        "\n\n",
        "\n",
    ]

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            name="code",
            display_name="Code Syntax & AST Splitter",
            description="Splits programming files along function, class, and comment block definitions while respecting syntax structure.",
            supported_mime_types=[
                "application/x-python",
                "text/x-python",
                "application/javascript",
                "application/json",
                "text/x-go",
                "text/x-sql",
            ],
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
        # Delegate to recursive splitter tuned with code block separators
        recursive_code = RecursiveChunkSplitter(separators=self.BLOCK_SEPARATORS)
        raw_dtos = recursive_code.split_text(
            text, max_characters, overlap_characters, base_meta
        )

        # Annotate metadata
        for dto in raw_dtos:
            dto.metadata_json["is_code_block"] = True
            if "class " in dto.content[:50] or "def " in dto.content[:50]:
                dto.metadata_json["has_definition"] = True
        return raw_dtos
