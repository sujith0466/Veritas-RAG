"""Extractors package export (`registry`, `base`, and concrete implementations)."""

from .base import BaseExtractor, ExtractedContent, ExtractorCapability
from .docx_extractor import DOCXExtractor
from .normalizer import normalize_text, detect_language
from .pdf_extractor import PDFExtractor
from .registry import ExtractorCapabilityRegistry
from .text_extractor import PlainTextExtractor
from .unstructured_extractor import UnstructuredExtractor


def create_default_registry() -> ExtractorCapabilityRegistry:
    """Create and initialize an ExtractorCapabilityRegistry with default enabled extractors."""
    registry = ExtractorCapabilityRegistry()
    registry.register(PlainTextExtractor())
    registry.register(PDFExtractor())
    registry.register(DOCXExtractor())
    registry.register(UnstructuredExtractor())
    return registry


__all__ = [
    "BaseExtractor",
    "DOCXExtractor",
    "ExtractedContent",
    "ExtractorCapability",
    "ExtractorCapabilityRegistry",
    "PDFExtractor",
    "PlainTextExtractor",
    "UnstructuredExtractor",
    "create_default_registry",
    "normalize_text",
    "detect_language",
]
