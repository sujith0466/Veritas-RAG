"""Docling OCR engine (`DoclingOCREngine`).

Integration hook for advanced document layout and OCR via Docling.
"""

from typing import BinaryIO

from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

from .base import OCREngine, OCRResult


class DoclingOCREngine(OCREngine):
    """Docling advanced OCR and layout engine abstraction."""

    @property
    def engine_name(self) -> str:
        return "docling"

    async def process(self, stream: BinaryIO, filename: str) -> OCRResult:
        try:
            import docling

            raise NotImplementedError("Docling native processing hook prepared.")
        except ImportError:
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_002,
                message="Docling OCR engine is not available (`docling` package not installed).",
                detail={"engine": self.engine_name},
            )
        except Exception as e:
            if isinstance(e, DocumentDomainException):
                raise
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_001,
                message=f"Docling OCR processing failed: {e}",
                detail={"filename": filename, "error": str(e)},
            ) from e
