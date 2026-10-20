"""Tesseract OCR engine (`TesseractOCREngine`).

Integration hook for `pytesseract` and system tesseract binary.
"""

from typing import BinaryIO

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

from .base import OCREngine, OCRResult


class TesseractOCREngine(OCREngine):
    """Tesseract OCR engine implementation (`pytesseract`)."""

    @property
    def engine_name(self) -> str:
        return "tesseract"

    async def process(
        self, stream: BinaryIO, filename: str, timeout_seconds: float | None = None
    ) -> OCRResult:
        try:
            import asyncio
            import io

            from PIL import Image
            import pytesseract

            current_pos = stream.tell()
            stream.seek(0)
            img_bytes = stream.read()
            stream.seek(current_pos)

            def _run_tesseract_sync() -> tuple[str, list[str], int]:
                t_val = timeout_seconds if timeout_seconds is not None and timeout_seconds > 0 else 0

                # Check if input is a PDF (PDF magic bytes `%PDF-`)
                if img_bytes.startswith(b"%PDF-"):
                    try:
                        import pypdfium2 as pdfium
                    except ImportError:
                        raise DocumentDomainException(
                            code=DocumentErrorCode.OCR_002,
                            message="PDF OCR requires `pypdfium2` for rasterization.",
                            detail={"engine": self.engine_name},
                        )

                    pdf = pdfium.PdfDocument(io.BytesIO(img_bytes))
                    all_text: list[str] = []
                    all_words: list[str] = []
                    page_count = len(pdf)
                    try:
                        for page in pdf:
                            image = page.render(scale=2).to_pil()
                            try:
                                page_text = pytesseract.image_to_string(image, timeout=t_val) or ""
                                all_text.append(page_text)
                                all_words.extend(page_text.split())
                            finally:
                                image.close()
                    finally:
                        pdf.close()
                    return "\n\n".join(all_text), all_words, max(1, page_count)

                # Open image from in-memory bytes and run pytesseract with subprocess timeout
                img = Image.open(io.BytesIO(img_bytes))
                try:
                    # Pass timeout (in integer/float seconds) directly to pytesseract subprocess call
                    text_out = pytesseract.image_to_string(img, timeout=t_val) or ""
                    words_out = text_out.split()
                    return text_out, words_out, 1
                finally:
                    img.close()

            # Offload blocking image decode and subprocess execution to worker thread
            text, words, page_count = await asyncio.to_thread(_run_tesseract_sync)

            return OCRResult(
                text=text.strip(),
                page_count=page_count,
                word_count=len(words),
                confidence=0.85 if words else 0.0,
                engine_used=self.engine_name,
            )
        except asyncio.CancelledError:
            # Re-raise cancellation cleanly without masking as generic OCR error
            raise
        except ImportError:
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_002,
                message="Tesseract OCR engine is not available (`pytesseract` / `Pillow` not installed).",
                detail={"engine": self.engine_name},
            )
        except RuntimeError as e:
            # pytesseract raises RuntimeError('Tesseract process timeout') when timeout expires
            if "timeout" in str(e).lower():
                raise DocumentDomainException(
                    code=DocumentErrorCode.OCR_TIMEOUT,
                    message=f"Tesseract OCR processing timed out after {timeout_seconds} seconds: {e}",
                    detail={"filename": filename, "timeout_seconds": timeout_seconds, "engine": self.engine_name},
                ) from e
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_001,
                message=f"Tesseract OCR processing failed: {e}",
                detail={"filename": filename, "error": str(e)},
            ) from e
        except DocumentDomainException:
            raise
        except Exception as e:
            if "timeout" in str(e).lower():
                raise DocumentDomainException(
                    code=DocumentErrorCode.OCR_TIMEOUT,
                    message=f"Tesseract OCR processing timed out: {e}",
                    detail={"filename": filename, "timeout_seconds": timeout_seconds, "engine": self.engine_name},
                ) from e
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_001,
                message=f"Tesseract OCR processing failed: {e}",
                detail={"filename": filename, "error": str(e)},
            ) from e
