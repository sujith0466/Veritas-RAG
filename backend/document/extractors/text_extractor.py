"""Plain Text and structured text extractor (`PlainTextExtractor`).

Extracts UTF-8 / ASCII content from `.txt`, `.md`, `.csv`, `.json` files.
"""

from typing import BinaryIO

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

from .base import BaseExtractor, ExtractedContent, ExtractorCapability


class PlainTextExtractor(BaseExtractor):
    """Extractor for standard plain-text, markdown, CSV, and JSON documents."""

    @property
    def capability(self) -> ExtractorCapability:
        return ExtractorCapability(
            name="PlainTextExtractor",
            supported_mimes={
                "text/plain",
                "text/markdown",
                "text/csv",
                "application/csv",
                "application/json",
            },
            supported_extensions={".txt", ".md", ".csv", ".json"},
            priority=10,
            enabled=True,
        )

    async def extract(
        self, stream: BinaryIO, filename: str, mime_type: str
    ) -> ExtractedContent:
        try:
            current_pos = stream.tell()
            stream.seek(0)
            raw_bytes = stream.read()
            stream.seek(current_pos)

            # Try UTF-8 first, fallback to latin-1
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin-1", errors="replace")

            # Clean and count
            words = text.split()
            word_count = len(words)
            # Estimate pages (~3000 chars or ~500 words per page, minimum 1)
            page_count = max(1, (len(text) + 2999) // 3000)

            return ExtractedContent(
                text=text,
                word_count=word_count,
                page_count=page_count,
                metadata={"character_count": len(text), "encoding_used": "utf-8"},
                language="en",  # Default placeholder for phase 1 text
                needs_ocr=False,
            )
        except Exception as e:
            if isinstance(e, DocumentDomainException):
                raise
            raise DocumentDomainException(
                code=DocumentErrorCode.EXTRACT_001,
                message=f"Failed to extract text from plain document: {e}",
                detail={"filename": filename, "error": str(e)},
            ) from e
