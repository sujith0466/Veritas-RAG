"""PDF Document Extractor (`PDFExtractor`).

Extracts text and page metadata from PDF files using `pypdf`.
If extracted text falls below minimal word density thresholds (<50 words),
sets `needs_ocr = True` to trigger OCR fallback (`EXTRACT_002`).
"""

import io
from typing import BinaryIO

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

from .base import BaseExtractor, ExtractedContent, ExtractorCapability

# Minimal word threshold below which a PDF is considered scanned/image-heavy
MIN_WORD_THRESHOLD = 50


class PDFExtractor(BaseExtractor):
    """PDF text and structure extractor with OCR fallback detection."""

    @property
    def capability(self) -> ExtractorCapability:
        return ExtractorCapability(
            name="PDFExtractor",
            supported_mimes={"application/pdf"},
            supported_extensions={".pdf"},
            priority=20,
            enabled=True,
        )

    async def extract(
        self, stream: BinaryIO, filename: str, mime_type: str
    ) -> ExtractedContent:
        try:
            current_pos = stream.tell()
            stream.seek(0)
            pdf_bytes = stream.read()
            stream.seek(current_pos)

            # Try pypdf extraction if available, otherwise fallback to minimal parsing
            extracted_pages: list[str] = []
            page_count = 0
            metadata: dict[str, Any] = {}

            try:
                import pypdf

                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                page_count = len(reader.pages)
                if reader.metadata:
                    metadata = {
                        k.lstrip("/"): str(v) for k, v in reader.metadata.items() if v
                    }

                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    extracted_pages.append(page_text)
            except ImportError:
                # If pypdf not installed, raise specific extraction error
                raise DocumentDomainException(
                    code=DocumentErrorCode.EXTRACT_001,
                    message="PDFExtractor requires `pypdf` package which is not installed.",
                )
            except Exception as e:
                raise DocumentDomainException(
                    code=DocumentErrorCode.EXTRACT_001,
                    message=f"Corrupted or unreadable PDF document structure: {e}",
                    detail={"filename": filename, "error": str(e)},
                ) from e

            full_text = "\n\n".join(extracted_pages).strip()
            words = full_text.split()
            word_count = len(words)

            needs_ocr = word_count < MIN_WORD_THRESHOLD
            if needs_ocr and word_count == 0:
                # Note: We do not fail fatally; we flag needs_ocr for OCR fallback
                metadata["scanned_pdf_detected"] = True

            return ExtractedContent(
                text=full_text,
                word_count=word_count,
                page_count=page_count,
                metadata=metadata,
                language="en",
                needs_ocr=needs_ocr,
            )
        except Exception as e:
            if isinstance(e, DocumentDomainException):
                raise
            raise DocumentDomainException(
                code=DocumentErrorCode.EXTRACT_001,
                message=f"Unexpected error during PDF extraction: {e}",
                detail={"filename": filename, "error": str(e)},
            ) from e
