"""Unstructured.io powered extraction engine (`UnstructuredExtractor`).

Supports complex document structures, tables, images, and OCR.
"""

from typing import BinaryIO
from unstructured.partition.auto import partition
from unstructured.documents.elements import Text, Table, Element

from backend.document.extractors.base import BaseExtractor, ExtractionResult


class UnstructuredExtractor(BaseExtractor):
    """Extractor leveraging unstructured.io for advanced parsing."""

    def __init__(self, use_ocr: bool = False, ocr_languages: list[str] | None = None):
        self.use_ocr = use_ocr
        self.ocr_languages = ocr_languages or ["eng"]

    def extract(self, file_obj: BinaryIO, metadata: dict | None = None) -> ExtractionResult:
        """Extract elements using unstructured."""
        file_obj.seek(0)
        
        # Determine strategy based on OCR requirement
        strategy = "hi_res" if self.use_ocr else "fast"
        languages = "+".join(self.ocr_languages) if self.use_ocr else None

        elements = partition(
            file=file_obj,
            strategy=strategy,
            languages=languages if self.use_ocr else None,
            pdf_infer_table_structure=True,
        )

        content_parts = []
        element_types = set()

        for el in elements:
            # We preserve tables as HTML if available, otherwise just text
            if isinstance(el, Table) and hasattr(el.metadata, "text_as_html"):
                content_parts.append(el.metadata.text_as_html)
            else:
                content_parts.append(str(el))
            
            element_types.add(type(el).__name__)

        raw_text = "\n\n".join(content_parts)

        return ExtractionResult(
            raw_text=raw_text,
            metadata={
                "extractor": "unstructured",
                "strategy": strategy,
                "element_types": list(element_types),
                "ocr_used": self.use_ocr,
                "languages": self.ocr_languages,
            },
        )
