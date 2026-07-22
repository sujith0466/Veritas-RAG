"""Base Extractor interfaces and capability models.

Defines the contract for pluggable document extraction engines.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, BinaryIO


@dataclass
class ExtractedContent:
    """Standardized output produced by a document extractor."""

    text: str
    word_count: int
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    language: str | None = None
    needs_ocr: bool = False


@dataclass
class ExtractorCapability:
    """Capability descriptor and routing metadata for an extractor implementation."""

    name: str
    supported_mimes: set[str]
    supported_extensions: set[str]
    priority: int = 10  # Higher value = higher priority selection
    enabled: bool = True


class BaseExtractor(ABC):
    """Abstract base class for all document content extractors (`ADR-005`)."""

    @property
    @abstractmethod
    def capability(self) -> ExtractorCapability:
        """Return the extractor's capability descriptor."""
        ...

    @abstractmethod
    async def extract(
        self, stream: BinaryIO, filename: str, mime_type: str
    ) -> ExtractedContent:
        """Extract plain text, structural metadata, and metrics from the binary stream.

        Returns:
            ExtractedContent containing normalized text and layout stats.

        Raises:
            DocumentDomainException(EXTRACT_001): On parsing corruption or unrecoverable error.
        """
        ...
