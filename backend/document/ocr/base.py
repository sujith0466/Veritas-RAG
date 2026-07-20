"""Abstract OCR Engine interfaces and result models.

Provides standardized interface for fallback optical character recognition (`OCR_xxx`).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass
class OCRResult:
    """Standardized result returned by an OCR engine."""

    text: str
    page_count: int
    word_count: int
    confidence: float
    engine_used: str


class OCREngine(ABC):
    """Abstract base class for all optical character recognition engines (`ADR-005`)."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Name of the OCR engine."""
        ...

    @abstractmethod
    async def process(self, stream: BinaryIO, filename: str) -> OCRResult:
        """Perform OCR on the binary stream of an image or scanned document.

        Returns:
            OCRResult containing extracted text, word/page counts, and confidence score.

        Raises:
            DocumentDomainException(OCR_xxx): On execution failure or engine unavailability.
        """
        ...
