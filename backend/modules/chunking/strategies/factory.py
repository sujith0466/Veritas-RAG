"""Splitter Strategy Factory (`SplitterStrategyFactory`).

Dynamically registers all 7 strategies (`recursive`, `markdown`, `sentence`, `paragraph`,
`table`, `code`, `semantic`), resolves appropriate splitters by name or MIME type, and
exports strategy metadata descriptions (`ADR-005`).
"""

from backend.modules.chunking.schemas.chunk import StrategyInfoDTO
from backend.modules.chunking.schemas.errors import ChunkStrategyNotFound

from .base import BaseChunkSplitter
from .code import CodeChunkSplitter
from .markdown import MarkdownChunkSplitter
from .paragraph import ParagraphChunkSplitter
from .recursive import RecursiveChunkSplitter
from .semantic import SemanticChunkSplitterPlaceholder
from .sentence import SentenceChunkSplitter
from .table import TableChunkSplitter


class SplitterStrategyFactory:
    """Registry and factory resolving optimal chunking strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, BaseChunkSplitter] = {
            "recursive": RecursiveChunkSplitter(),
            "markdown": MarkdownChunkSplitter(),
            "sentence": SentenceChunkSplitter(),
            "paragraph": ParagraphChunkSplitter(),
            "table": TableChunkSplitter(),
            "code": CodeChunkSplitter(),
            "semantic": SemanticChunkSplitterPlaceholder(),
        }

    def get_splitter(
        self, strategy_name: str | None = None, mime_type: str | None = None
    ) -> BaseChunkSplitter:
        """Resolve splitter by explicit strategy name, or infer from MIME type (`text/markdown` -> `markdown`)."""
        if strategy_name:
            normalized = strategy_name.lower().strip()
            if normalized in self._strategies:
                return self._strategies[normalized]
            raise ChunkStrategyNotFound(
                message=f"Chunking strategy '{strategy_name}' is not registered or supported.",
                detail={
                    "requested": strategy_name,
                    "available": list(self._strategies.keys()),
                },
            )

        if mime_type:
            mime_lower = mime_type.lower().strip()
            # 1. Check exact table/csv matches
            if mime_lower in {
                "text/csv",
                "application/csv",
                "text/tab-separated-values",
            }:
                return self._strategies["table"]
            # 2. Check markdown
            if "markdown" in mime_lower:
                return self._strategies["markdown"]
            # 3. Check code
            if any(
                c in mime_lower for c in ("python", "javascript", "json", "go", "sql")
            ):
                return self._strategies["code"]

        # Default fallback is recursive character splitting
        return self._strategies["recursive"]

    def list_strategies(self) -> list[StrategyInfoDTO]:
        """Return canonical metadata descriptions for all registered strategies."""
        return [splitter.strategy_info for splitter in self._strategies.values()]
