"""Unit tests for chunking splitting strategies (`ADR-005`)."""

import pytest

from backend.modules.chunking.schemas.errors import ChunkStrategyNotFound
from backend.modules.chunking.strategies import (
    CodeChunkSplitter,
    MarkdownChunkSplitter,
    ParagraphChunkSplitter,
    RecursiveChunkSplitter,
    SemanticChunkSplitterPlaceholder,
    SentenceChunkSplitter,
    SplitterStrategyFactory,
    TableChunkSplitter,
    estimate_token_count,
)


class TestChunkingStrategies:
    """Test suite verifying all 7 splitting strategies and factory behavior."""

    def test_estimate_token_count(self) -> None:
        assert estimate_token_count("") == 0
        assert estimate_token_count("abcd") == 1
        assert estimate_token_count("abcdefgh") == 2
        assert estimate_token_count("Hello world from RAGuard") == 6

    def test_recursive_chunk_splitter_basic(self) -> None:
        splitter = RecursiveChunkSplitter()
        text = "This is paragraph one.\n\nThis is paragraph two.\n\nAnd paragraph three."
        chunks = splitter.split_text(text, max_characters=30, overlap_characters=5)
        assert len(chunks) >= 3
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert len(chunk.content) <= 35  # max_characters + minor overlap slack
            assert chunk.character_count == len(chunk.content)
            assert chunk.token_count > 0

    def test_markdown_chunk_splitter_breadcrumbs(self) -> None:
        splitter = MarkdownChunkSplitter()
        text = (
            "# Chapter 1\n"
            "Introduction text here.\n"
            "## Section 1.1\n"
            "Details about section 1.1.\n"
            "### Subsection 1.1.1\n"
            "Deep details inside subsection 1.1.1."
        )
        chunks = splitter.split_text(text, max_characters=500, overlap_characters=50)
        assert len(chunks) == 3

        # Check breadcrumbs
        assert chunks[0].section_path == ["# Chapter 1"]
        assert "Introduction text here." in chunks[0].content

        assert chunks[1].section_path == ["# Chapter 1", "## Section 1.1"]
        assert "Details about section 1.1." in chunks[1].content

        assert chunks[2].section_path == ["# Chapter 1", "## Section 1.1", "### Subsection 1.1.1"]
        assert "Deep details inside subsection 1.1.1." in chunks[2].content

    def test_sentence_chunk_splitter(self) -> None:
        splitter = SentenceChunkSplitter()
        text = "First sentence is here. Second sentence is here. Third sentence is right here! And a fourth?"
        chunks = splitter.split_text(text, max_characters=50, overlap_characters=10)
        assert len(chunks) >= 2
        assert all(c.content.endswith(".") or c.content.endswith("!") or c.content.endswith("?") for c in chunks)

    def test_paragraph_chunk_splitter(self) -> None:
        splitter = ParagraphChunkSplitter()
        text = "Block A line 1.\nBlock A line 2.\n\nBlock B line 1.\nBlock B line 2."
        chunks = splitter.split_text(text, max_characters=40, overlap_characters=0)
        assert len(chunks) == 2
        assert "Block A" in chunks[0].content
        assert "Block B" in chunks[1].content

    def test_table_chunk_splitter_prefixes_headers(self) -> None:
        splitter = TableChunkSplitter()
        text = (
            "| ID | Name | Role |\n"
            "|---|---|---|\n"
            "| 1 | Alice | Admin |\n"
            "| 2 | Bob | Engineer |\n"
            "| 3 | Charlie | Designer |\n"
            "| 4 | Dave | Manager |\n"
        )
        # Force small max_characters so rows get split into multiple chunks
        chunks = splitter.split_text(text, max_characters=60, overlap_characters=0)
        assert len(chunks) >= 2
        for chunk in chunks:
            # Every chunk MUST preserve the table header row
            assert "| ID | Name | Role |" in chunk.content
            assert chunk.metadata_json["has_table_headers"] is True

    def test_code_chunk_splitter_metadata(self) -> None:
        splitter = CodeChunkSplitter()
        code = (
            "class MyService:\n"
            "    def __init__(self):\n"
            "        pass\n\n"
            "def helper_func():\n"
            "    return True\n"
        )
        chunks = splitter.split_text(code, max_characters=500, overlap_characters=50)
        assert len(chunks) >= 1
        assert chunks[0].metadata_json.get("is_code_block") is True
        assert chunks[0].metadata_json.get("has_definition") is True

    def test_semantic_chunk_splitter_placeholder_raises_m2_error(self) -> None:
        splitter = SemanticChunkSplitterPlaceholder()
        assert splitter.strategy_info.status == "experimental"
        with pytest.raises(ChunkStrategyNotFound) as exc_info:
            splitter.split_text("Some text")
        assert "requires dense embedding vectors from the Milestone 2 Embedding Pipeline" in str(exc_info.value)
        assert exc_info.value.code == "CHK_002"

    def test_splitter_strategy_factory(self) -> None:
        factory = SplitterStrategyFactory()
        assert isinstance(factory.get_splitter("markdown"), MarkdownChunkSplitter)
        assert isinstance(factory.get_splitter("table"), TableChunkSplitter)
        assert isinstance(factory.get_splitter("code"), CodeChunkSplitter)
        assert isinstance(factory.get_splitter("semantic"), SemanticChunkSplitterPlaceholder)

        # MIME inference
        assert isinstance(factory.get_splitter(mime_type="text/markdown"), MarkdownChunkSplitter)
        assert isinstance(factory.get_splitter(mime_type="text/csv"), TableChunkSplitter)
        assert isinstance(factory.get_splitter(mime_type="application/x-python"), CodeChunkSplitter)
        assert isinstance(factory.get_splitter(mime_type="text/plain"), RecursiveChunkSplitter)

        # Unsupported strategy raises CHK_002
        with pytest.raises(ChunkStrategyNotFound):
            factory.get_splitter("unsupported_magic_strategy")

        infos = factory.list_strategies()
        all_infos = infos.supported + infos.experimental + infos.disabled
        assert len(all_infos) == 8
        names = {i.id for i in all_infos}
        assert names == {"recursive", "markdown", "sentence", "paragraph", "table", "code", "semantic", "fixed_size"}
