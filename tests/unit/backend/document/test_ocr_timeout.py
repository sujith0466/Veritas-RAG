"""Unit tests for OCR Pipeline Timeout Bounding and Configuration (P0-4).

Verifies:
1. Default OCR timeout and environment variable override.
2. Rejection of invalid timeout configuration.
3. Successful OCR execution within deadline.
4. Timeout of a slow engine triggering DocumentErrorCode.OCR_TIMEOUT ("OCR_003").
5. Cumulative deadline bounding across multiple sequential engines (no timeout stacking).
6. Tesseract subprocess timeout translation, thread offloading, and resource cleanup.
7. Event loop responsiveness while synchronous OCR executes in thread.
8. Clean cancellation propagation without masking as generic error.
9. Timeout error classification as FATAL and prevention of Celery exponential retries.
10. Initial version (V1) failure behavior transitioning Document to FAILED.
11. Multi-version serving protection: preserving active V1 READY status when in-flight V2 OCR times out.
12. Seamless fallback to subsequent engine when primary engine fails without timeout.
"""

import asyncio
import io
import time
from typing import BinaryIO
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from PIL import Image
from pydantic import ValidationError
import pytest

from backend.core.config import get_settings
from backend.core.config.ocr import OCRSettings
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.ocr.base import OCREngine, OCRResult
from backend.document.ocr.pipeline import OCRPipeline
from backend.document.ocr.tesseract import TesseractOCREngine
from backend.document.schemas.errors import (
    DocumentDomainException,
    DocumentErrorCode,
    ErrorSeverity,
    get_error_severity,
)
from backend.document.services.failure_service import PipelineFailureSynchronizer
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding


# ── Test Engines ──────────────────────────────────────────────────────────────

class MockFastEngine(OCREngine):
    """Engine that completes promptly with valid text."""

    @property
    def engine_name(self) -> str:
        return "fast_engine"

    async def process(
        self, stream: BinaryIO, filename: str, timeout_seconds: float | None = None
    ) -> OCRResult:
        return OCRResult(
            text="Scanned document content extracted successfully",
            page_count=1,
            word_count=5,
            confidence=0.95,
            engine_used=self.engine_name,
        )


class MockSlowEngine(OCREngine):
    """Engine that simulates an unresponsive or hung OCR operation."""

    def __init__(self, delay: float = 2.0) -> None:
        self.delay = delay

    @property
    def engine_name(self) -> str:
        return "slow_engine"

    async def process(
        self, stream: BinaryIO, filename: str, timeout_seconds: float | None = None
    ) -> OCRResult:
        await asyncio.sleep(self.delay)
        return OCRResult(
            text="Completed after delay",
            page_count=1,
            word_count=3,
            confidence=0.80,
            engine_used=self.engine_name,
        )


class MockFailingEngine(OCREngine):
    """Engine that fails immediately with a standard engine exception."""

    @property
    def engine_name(self) -> str:
        return "failing_engine"

    async def process(
        self, stream: BinaryIO, filename: str, timeout_seconds: float | None = None
    ) -> OCRResult:
        raise DocumentDomainException(
            code=DocumentErrorCode.OCR_001,
            message="Primary engine syntax failure",
            detail={"engine": self.engine_name},
        )


# ── Configuration Tests ───────────────────────────────────────────────────────

def test_ocr_settings_defaults():
    """Verify default OCR timeout is 30.0s."""
    settings = OCRSettings()
    assert settings.timeout_seconds == 30.0


def test_ocr_settings_env_override(monkeypatch):
    """Verify OCR_TIMEOUT_SECONDS overrides default."""
    monkeypatch.setenv("OCR_TIMEOUT_SECONDS", "45.5")
    settings = OCRSettings()
    assert settings.timeout_seconds == 45.5


def test_ocr_settings_bounds_validation():
    """Verify OCR timeout rejects values outside [1.0, 300.0]."""
    with pytest.raises(ValidationError):
        OCRSettings(timeout_seconds=0.5)

    with pytest.raises(ValidationError):
        OCRSettings(timeout_seconds=301.0)

    valid_low = OCRSettings(timeout_seconds=1.0)
    assert valid_low.timeout_seconds == 1.0

    valid_high = OCRSettings(timeout_seconds=300.0)
    assert valid_high.timeout_seconds == 300.0


# ── Pipeline Timeout & Fallback Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_ocr_pipeline_fast_path():
    """Verify successful OCR completes within deadline."""
    pipeline = OCRPipeline(engines=[MockFastEngine()])
    stream = io.BytesIO(b"dummy image data")
    res = await pipeline.execute(stream, "test.png", timeout_seconds=5.0)

    assert res.word_count == 5
    assert res.engine_used == "fast_engine"
    assert "Scanned document" in res.text


@pytest.mark.asyncio
async def test_ocr_pipeline_slow_engine_times_out():
    """Verify slow engine exceeding deadline raises OCR_TIMEOUT ("OCR_003")."""
    pipeline = OCRPipeline(engines=[MockSlowEngine(delay=0.5)])
    stream = io.BytesIO(b"dummy image data")

    t0 = time.monotonic()
    with pytest.raises(DocumentDomainException) as exc_info:
        await pipeline.execute(stream, "heavy.png", timeout_seconds=0.1)
    elapsed = time.monotonic() - t0

    assert exc_info.value.code == DocumentErrorCode.OCR_TIMEOUT
    assert "timed out after" in exc_info.value.message
    # Assert timeout fired promptly (allowing small scheduler jitter)
    assert elapsed < 0.35


@pytest.mark.asyncio
async def test_ocr_pipeline_cumulative_budget_no_stacking():
    """Verify sequential fallback engines consume the single cumulative budget."""
    # Engine 1 takes 0.15s then fails; total budget is 0.20s; Engine 2 wants 0.15s
    class Engine1DelayThenFail(OCREngine):
        @property
        def engine_name(self) -> str:
            return "engine1"

        async def process(self, stream, filename, timeout_seconds=None):
            await asyncio.sleep(0.12)
            raise DocumentDomainException(code=DocumentErrorCode.OCR_001, message="Engine 1 crashed")

    class Engine2Slow(OCREngine):
        @property
        def engine_name(self) -> str:
            return "engine2"

        async def process(self, stream, filename, timeout_seconds=None):
            await asyncio.sleep(0.15)
            return OCRResult(text="late", page_count=1, word_count=1, confidence=0.5, engine_used="engine2")

    pipeline = OCRPipeline(engines=[Engine1DelayThenFail(), Engine2Slow()])
    stream = io.BytesIO(b"dummy")

    t0 = time.monotonic()
    with pytest.raises(DocumentDomainException) as exc_info:
        # Total budget 0.18s
        await pipeline.execute(stream, "stacked.png", timeout_seconds=0.18)
    elapsed = time.monotonic() - t0

    assert exc_info.value.code == DocumentErrorCode.OCR_TIMEOUT
    # Ensure total elapsed does NOT equal 0.12 + 0.15 = 0.27s (no timeout stacking)
    assert elapsed < 0.25


@pytest.mark.asyncio
async def test_ocr_pipeline_fallback_success_within_deadline():
    """Verify fallback to secondary engine succeeds if primary fails within deadline."""
    pipeline = OCRPipeline(engines=[MockFailingEngine(), MockFastEngine()])
    stream = io.BytesIO(b"dummy")

    res = await pipeline.execute(stream, "fallback.png", timeout_seconds=2.0)
    assert res.engine_used == "fast_engine"
    assert res.word_count == 5


# ── Tesseract Engine Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tesseract_engine_subprocess_timeout_translation():
    """Verify pytesseract subprocess timeout raises DocumentErrorCode.OCR_TIMEOUT."""
    engine = TesseractOCREngine()

    img = Image.new("RGB", (10, 10), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    mock_pytesseract = MagicMock()
    mock_pytesseract.image_to_string.side_effect = RuntimeError("Tesseract process timeout")

    with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
        with pytest.raises(DocumentDomainException) as exc_info:
            await engine.process(buf, "scan.png", timeout_seconds=2.0)

    assert exc_info.value.code == DocumentErrorCode.OCR_TIMEOUT
    assert "timed out after 2.0 seconds" in exc_info.value.message


@pytest.mark.asyncio
async def test_tesseract_engine_passes_timeout_to_subprocess():
    """Verify TesseractOCREngine passes timeout_seconds to pytesseract.image_to_string."""
    engine = TesseractOCREngine()

    img = Image.new("RGB", (10, 10), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    mock_pytesseract = MagicMock()
    mock_pytesseract.image_to_string.return_value = "recognized words"

    with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
        res = await engine.process(buf, "page.png", timeout_seconds=12.5)
        mock_pytesseract.image_to_string.assert_called_once()
        assert mock_pytesseract.image_to_string.call_args.kwargs["timeout"] == 12.5
        assert res.word_count == 2
        assert res.text == "recognized words"


@pytest.mark.asyncio
async def test_tesseract_engine_re_raises_cancellation():
    """Verify external task cancellation is cleanly propagated and not swallowed."""
    engine = TesseractOCREngine()
    stream = io.BytesIO(b"dummy")

    mock_pytesseract = MagicMock()

    async def _cancel_soon(*args, **kwargs):
        await asyncio.sleep(0.01)
        raise asyncio.CancelledError()

    with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
        with patch("asyncio.to_thread", side_effect=_cancel_soon):
            with pytest.raises(asyncio.CancelledError):
                await engine.process(stream, "cancel.png", timeout_seconds=5.0)


@pytest.mark.asyncio
async def test_tesseract_engine_event_loop_responsiveness():
    """Verify event loop remains responsive while OCR is executing in thread."""
    engine = TesseractOCREngine()

    # Provide valid 10x10 PNG bytes
    img = Image.new("RGB", (10, 10), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    mock_pytesseract = MagicMock()
    def _slow_sync(*args, **kwargs):
        time.sleep(0.1)
        return "ocr done"

    mock_pytesseract.image_to_string.side_effect = _slow_sync

    heartbeat_ticks = 0
    async def _heartbeat():
        nonlocal heartbeat_ticks
        for _ in range(5):
            await asyncio.sleep(0.02)
            heartbeat_ticks += 1

    with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
        # Run OCR process concurrently with async heartbeat
        ocr_task = asyncio.create_task(engine.process(buf, "loop.png", timeout_seconds=1.0))
        hb_task = asyncio.create_task(_heartbeat())

        res, _ = await asyncio.gather(ocr_task, hb_task)
        assert res.text == "ocr done"
        # Heartbeats must have fired while OCR was running in worker thread
        assert heartbeat_ticks >= 3


# ── Error Severity & Failure Synchronization Tests ───────────────────────────

def test_ocr_timeout_severity_is_fatal():
    """Verify OCR_TIMEOUT is mapped to FATAL to prevent repeated Celery retries."""
    assert get_error_severity(DocumentErrorCode.OCR_TIMEOUT) == ErrorSeverity.FATAL
    # Verify ordinary engine failure remains RECOVERABLE
    assert get_error_severity(DocumentErrorCode.OCR_001) == ErrorSeverity.RECOVERABLE


@pytest.mark.asyncio
async def test_failure_synchronizer_ocr_timeout_initial_version_transitions_failed():
    """Verify OCR timeout on initial upload (V1, no active version) transitions document to FAILED."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="tenant-1",
        status=DocumentStatus.OCR,
        filename="scanned.pdf",
    )
    mock_job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        version_id=v1_id,
        status="PROCESSING",
        current_step="ocr",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        is_active_vector=False,
        is_deleted=False,
    )

    mock_session = AsyncMock()
    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job_id:
            return mock_job
        return None

    mock_session.get.side_effect = mock_get
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [v1]
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="ocr",
        error_code=DocumentErrorCode.OCR_TIMEOUT,
        error_message="OCR processing timed out after 30.0s",
        job_id=job_id,
        tenant_id="tenant-1",
        version_id=v1_id,
    )

    assert mock_doc.status == DocumentStatus.FAILED
    assert mock_job.status == "FAILED"
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_ocr_timeout_preserves_active_version():
    """Verify OCR timeout on V2 preserves active V1 READY status and fails only V2."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="tenant-1",
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="scanned.pdf",
    )
    mock_job2 = ProcessingJob(
        id=job2_id,
        document_id=doc_id,
        version_id=v2_id,
        status="PROCESSING",
        current_step="ocr",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        is_active_vector=True,  # Active serving version
        is_deleted=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        is_active_vector=False,
        is_deleted=False,
    )

    mock_session = AsyncMock()
    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job2_id:
            return mock_job2
        return None

    mock_session.get.side_effect = mock_get
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [v1, v2]
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="ocr",
        error_code=DocumentErrorCode.OCR_TIMEOUT,
        error_message="OCR processing timed out after 30.0s on version 2",
        job_id=job2_id,
        tenant_id="tenant-1",
        version_id=v2_id,
    )

    # Document remains READY for online RAG queries
    assert mock_doc.status == DocumentStatus.READY
    assert mock_doc.latest_version_id == v1_id
    # Only in-flight job2 marked FAILED
    assert mock_job2.status == "FAILED"
    mock_session.commit.assert_called()
