"""Tesseract OCR engine (`TesseractOCREngine`).

Integration hook for `pytesseract` and system tesseract binary.
"""

from typing import BinaryIO

from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

from .base import OCREngine, OCRResult


class TesseractOCREngine(OCREngine):
    """Tesseract OCR engine implementation (`pytesseract`)."""

    @property
    def engine_name(self) -> str:
        return "tesseract"

    async def process(self, stream: BinaryIO, filename: str) -> OCRResult:
        try:
            import io

            import pytesseract
            from PIL import Image

            current_pos = stream.tell()
            stream.seek(0)
            img_bytes = stream.read()
            stream.seek(current_pos)

            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img) or ""
            words = text.split()

            return OCRResult(
                text=text.strip(),
                page_count=1,
                word_count=len(words),
                confidence=0.85 if words else 0.0,
                engine_used=self.engine_name,
            )
        except ImportError:
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_002,
                message="Tesseract OCR engine is not available (`pytesseract` / `Pillow` not installed).",
                detail={"engine": self.engine_name},
            )
        except Exception as e:
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_001,
                message=f"Tesseract OCR processing failed: {e}",
                detail={"filename": filename, "error": str(e)},
            ) from e
