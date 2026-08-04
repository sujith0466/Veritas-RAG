"""Unstructured.io powered extraction engine (`UnstructuredExtractor`).

Supports complex document structures, tables, images, and OCR.
"""

from typing import Any, BinaryIO

try:
    from unstructured.documents.elements import Table
    from unstructured.partition.auto import partition
except ImportError:
    Table = None
    partition = None

from backend.document.extractors.base import BaseExtractor, ExtractedContent, ExtractorCapability


class UnstructuredExtractor(BaseExtractor):
    """Extractor leveraging unstructured.io for advanced parsing."""

    def __init__(self, use_ocr: bool = False, ocr_languages: list[str] | None = None):
        self.use_ocr = use_ocr
        self.ocr_languages = ocr_languages or ["eng"]

    @property
    def capability(self) -> ExtractorCapability:
        return ExtractorCapability(
            name="UnstructuredExtractor",
            supported_mimes={"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/html"},
            supported_extensions={".pdf", ".docx", ".html", ".htm"},
            priority=5,
            enabled=True,
        )

    async def extract(
        self, stream: BinaryIO, filename: str, mime_type: str
    ) -> ExtractedContent:
        """Extract elements using unstructured."""
        if partition is None:
            return ExtractedContent(
                text="",
                word_count=0,
                page_count=1,
                metadata={"error": "unstructured library not installed"},
                needs_ocr=False,
            )

        stream.seek(0)
        strategy = "hi_res" if self.use_ocr else "fast"
        languages = "+".join(self.ocr_languages) if self.use_ocr else None

        elements = partition(
            file=stream,
            strategy=strategy,
            languages=languages if self.use_ocr else None,
            pdf_infer_table_structure=True,
        )

        content_parts = []
        element_types = set()

        for el in elements:
            if Table is not None and isinstance(el, Table) and hasattr(el.metadata, "text_as_html"):
                content_parts.append(el.metadata.text_as_html)
            else:
                content_parts.append(str(el))

            element_types.add(type(el).__name__)

        raw_text = "\n\n".join(content_parts)
        words = len(raw_text.split())

        return ExtractedContent(
            text=raw_text,
            word_count=words,
            page_count=1,
            metadata={
                "extractor": "unstructured",
                "strategy": strategy,
                "element_types": list(element_types),
                "ocr_used": self.use_ocr,
                "languages": self.ocr_languages,
            },
            needs_ocr=False,
        )
