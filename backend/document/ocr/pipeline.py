import asyncio
import time
from typing import BinaryIO

import structlog

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

from .base import OCREngine, OCRResult
from .docling import DoclingOCREngine
from .tesseract import TesseractOCREngine

logger = structlog.get_logger(__name__)


class OCRPipeline:
    """Orchestrates OCR fallback execution (`Docling -> Tesseract`) with overall deadline bounding."""

    def __init__(
        self,
        engines: list[OCREngine] | None = None,
        default_timeout_seconds: float | None = None,
    ) -> None:
        self.engines = engines or [DoclingOCREngine(), TesseractOCREngine()]
        self.default_timeout_seconds = default_timeout_seconds

    async def execute(
        self,
        stream: BinaryIO,
        filename: str,
        timeout_seconds: float | None = None,
    ) -> OCRResult:
        """Run OCR across configured engines in priority order within an absolute deadline.

        Sequential fallback engines consume the same remaining time budget, rather than
        receiving a fresh full timeout. When the overall budget is exhausted, a structured
        DocumentErrorCode.OCR_TIMEOUT ("OCR_003") exception is raised.
        """
        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.default_timeout_seconds
        )

        # If no timeout configured, run unbounded across engines
        if effective_timeout is None or effective_timeout <= 0:
            return await self._execute_engines(stream, filename, None, None)

        start_time = time.monotonic()
        deadline = start_time + effective_timeout

        try:
            return await asyncio.wait_for(
                self._execute_engines(stream, filename, deadline, effective_timeout),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError as e:
            elapsed = time.monotonic() - start_time
            logger.warning(
                "OCR pipeline execution deadline exceeded",
                filename=filename,
                timeout_seconds=effective_timeout,
                elapsed_seconds=round(elapsed, 3),
            )
            raise DocumentDomainException(
                code=DocumentErrorCode.OCR_TIMEOUT,
                message=f"OCR pipeline timed out after {effective_timeout}s for file '{filename}'.",
                detail={
                    "filename": filename,
                    "timeout_seconds": effective_timeout,
                    "elapsed_seconds": round(elapsed, 3),
                },
            ) from e

    async def _execute_engines(
        self,
        stream: BinaryIO,
        filename: str,
        deadline: float | None,
        total_timeout: float | None,
    ) -> OCRResult:
        """Internal execution loop across engines with monotonic remaining-budget checks."""
        last_error: Exception | None = None

        for engine in self.engines:
            # Monotonic time check before attempting next engine
            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DocumentDomainException(
                        code=DocumentErrorCode.OCR_TIMEOUT,
                        message=f"OCR pipeline budget exhausted before invoking engine '{engine.engine_name}'.",
                        detail={
                            "filename": filename,
                            "engine": engine.engine_name,
                            "total_timeout": total_timeout,
                        },
                    )

            try:
                result = await engine.process(stream, filename, timeout_seconds=remaining)
                if result.word_count > 0:
                    return result
            except DocumentDomainException as e:
                # If an engine explicitly timed out, do not swallow it as an ordinary engine failure
                if e.code == DocumentErrorCode.OCR_TIMEOUT:
                    raise
                last_error = e
                continue
            except asyncio.CancelledError:
                raise
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
