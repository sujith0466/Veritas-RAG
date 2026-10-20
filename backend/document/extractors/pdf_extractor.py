"""PDF Document Extractor (`PDFExtractor`).

Extracts text and page metadata from PDF files using `pypdf`.
If extracted text falls below minimal word density thresholds (<50 words),
sets `needs_ocr = True` to trigger OCR fallback (`EXTRACT_002`).
"""

import asyncio
import io
from typing import Any, BinaryIO

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

            def _extract_sync() -> tuple[list[str], int, dict[str, Any]]:
                try:
                    import pypdf

                    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                    p_count = len(reader.pages)
                    meta: dict[str, Any] = {}
                    if reader.metadata:
                        meta = {
                            k.lstrip("/"): str(v) for k, v in reader.metadata.items() if v
                        }

                    pages: list[str] = []
                    for page in reader.pages:
                        page_text = page.extract_text() or ""
                        pages.append(page_text)
                    return pages, p_count, meta
                except ImportError:
                    raise DocumentDomainException(
                        code=DocumentErrorCode.EXTRACT_001,
                        message="PDFExtractor requires `pypdf` package which is not installed.",
                    )
                except Exception as e:
                    if isinstance(e, DocumentDomainException):
                        raise
                    raise DocumentDomainException(
                        code=DocumentErrorCode.EXTRACT_001,
                        message=f"Corrupted or unreadable PDF document structure: {e}",
                        detail={"filename": filename, "error": str(e)},
                    ) from e

            # Offload synchronous, CPU-bound PDF extraction to worker thread to avoid blocking event loop
            extracted_pages, page_count, metadata = await asyncio.to_thread(_extract_sync)

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
