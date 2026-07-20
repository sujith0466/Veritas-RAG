"""OCR package export (`base`, `engines`, and `pipeline`)."""

from .base import OCREngine, OCRResult
from .docling import DoclingOCREngine
from .pipeline import OCRPipeline
from .tesseract import TesseractOCREngine

__all__ = [
    "DoclingOCREngine",
    "OCREngine",
    "OCRPipeline",
    "OCRResult",
    "TesseractOCREngine",
]
