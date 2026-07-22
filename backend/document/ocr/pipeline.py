"""Orchestrated OCR Pipeline (`OCRPipeline`).

Executes primary OCR engine with seamless fallback to secondary engine upon error or low confidence.
"""

from typing import BinaryIO

from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

from .base import OCREngine, OCRResult
from .docling import DoclingOCREngine
from .tesseract import TesseractOCREngine


class OCRPipeline:
    """Orchestrates OCR fallback execution (`Docling -> Tesseract`)."""

    def __init__(self, engines: list[OCREngine] | None = None) -> None:
        self.engines = engines or [DoclingOCREngine(), TesseractOCREngine()]

    async def execute(self, stream: BinaryIO, filename: str) -> OCRResult:
        """Run OCR across configured engines in priority order until successful (`OCR_001`, `OCR_002`)."""
        last_error: Exception | None = None

        for engine in self.engines:
            try:
                result = await engine.process(stream, filename)
                if result.word_count > 0:
                    return result
            except DocumentDomainException as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        if last_error:
            if isinstance(last_error, DocumentDomainException):
                raise last_error
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_001,
                message=f"All OCR engines failed to process document: {last_error}",
                detail={"filename": filename, "error": str(last_error)},
            ) from last_error

        raise DocumentDomainException(
            code=DocumentErrorCode.OCR_002,
            message="No OCR engines configured or capable of extracting text.",
            detail={"filename": filename},
        )
