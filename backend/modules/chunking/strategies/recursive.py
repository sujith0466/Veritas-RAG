"""Recursive Character Chunk Splitter.

Splits text along a descending hierarchy of separators (`\n\n`, `\n`, `. `, ` `, ``)
to preserve paragraphs and semantic sentences before breaking across raw words or characters.
"""

from typing import Any

from backend.modules.chunking.schemas.chunk import ChunkDTO, StrategyInfoDTO

from .base import BaseChunkSplitter, estimate_token_count


class RecursiveChunkSplitter(BaseChunkSplitter):
    """Standard hierarchical separator splitter applicable to general prose (`recursive`)."""

    def __init__(self, separators: list[str] | None = None) -> None:
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    @property
    def strategy_info(self) -> StrategyInfoDTO:
        return StrategyInfoDTO(
            name="recursive",
            display_name="Recursive Character Splitter",
            description="Hierarchically splits on paragraphs, newlines, sentences, and words while maintaining overlap.",
            supported_mime_types=["*"],
            default_max_characters=1000,
            default_overlap_characters=200,
            is_placeholder=False,
        )

    def split_text(
        self,
        text: str,
        max_characters: int = 1000,
        overlap_characters: int = 200,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkDTO]:
        if not text or not text.strip():
            return []

        base_meta = base_metadata or {}
        raw_chunks = self._split_recursive(
            text, max_characters, overlap_characters, self.separators
        )

        # Post-process into ChunkDTOs with index and token gauges
        dtos: list[ChunkDTO] = []
        for idx, chunk_text in enumerate(raw_chunks):
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

    def _split_recursive(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        separators: list[str],
    ) -> list[str]:
        final_chunks: list[str] = []
        separator = separators[-1]
        new_separators = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1 :]
                break

        splits = _split_text_with_separator(text, separator)
        good_splits: list[str] = []

        for s in splits:
            if len(s) < chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = _merge_splits(
                        good_splits, separator, chunk_size, chunk_overlap
                    )
                    final_chunks.extend(merged)
                    good_splits = []
                if not new_separators:
                    # Absolute character slicing fallback when no more separators exist
                    for i in range(0, len(s), max(1, chunk_size - chunk_overlap)):
                        sub = s[i : i + chunk_size]
                        if sub:
                            final_chunks.append(sub)
                else:
                    sub_chunks = self._split_recursive(
                        s, chunk_size, chunk_overlap, new_separators
                    )
                    final_chunks.extend(sub_chunks)

        if good_splits:
            merged = _merge_splits(good_splits, separator, chunk_size, chunk_overlap)
            final_chunks.extend(merged)

        return final_chunks


def _split_text_with_separator(text: str, separator: str) -> list[str]:
    if separator:
        return text.split(separator)
    return list(text)


def _merge_splits(
    splits: list[str], separator: str, chunk_size: int, chunk_overlap: int
) -> list[str]:
    docs: list[str] = []
    current_doc: list[str] = []
    total_len = 0

    for s in splits:
        len_s = len(s)
        if total_len + len_s + (len(separator) if current_doc else 0) > chunk_size:
            if total_len > 0:
                doc = separator.join(current_doc)
                if doc:
                    docs.append(doc)
                # Trim splits from front until within overlap budget
                while total_len > chunk_overlap or (
                    total_len + len_s + (len(separator) if current_doc else 0)
                    > chunk_size
                    and total_len > 0
                ):
                    total_len -= len(current_doc[0]) + (
                        len(separator) if len(current_doc) > 1 else 0
                    )
                    current_doc.pop(0)
        current_doc.append(s)
        total_len += len_s + (len(separator) if len(current_doc) > 1 else 0)

    if current_doc:
        doc = separator.join(current_doc)
        if doc:
            docs.append(doc)
    return docs
