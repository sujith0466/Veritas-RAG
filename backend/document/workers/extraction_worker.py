"""Extraction worker (`extraction_worker.py`).

Celery worker task that delegates to unstructured/extractors based on document version requirements.
"""

import asyncio
from datetime import UTC, datetime
import os
import uuid

from celery import shared_task
import structlog

from backend.cache.client import get_redis_client
from backend.database.engine import get_session_factory
from backend.document.extractors.normalizer import detect_language, normalize_text
from backend.document.extractors.unstructured_extractor import UnstructuredExtractor
from backend.document.metrics.job_metrics import STEP_DURATION_SECONDS
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.repositories.job_audit_repository import JobAuditRepository
from backend.document.repositories.job_repository import JobRepository
from backend.document.repositories.job_step_repository import JobStepRepository
from backend.document.services.processing_job_service import ProcessingJobService

logger = structlog.get_logger(__name__)


@shared_task(name="jobs.process_extraction", bind=True, max_retries=3)
def process_extraction(self, job_id_str: str, version_id_str: str, file_path: str):
    """Worker task to perform text extraction and OCR."""
    job_id = uuid.UUID(job_id_str)
    version_id = uuid.UUID(version_id_str)

    async def run():
        redis_client = get_redis_client()
        session_factory = get_session_factory()
        async with session_factory() as session:
            job_repo = JobRepository()
            job_service = ProcessingJobService(
                job_repo, JobStepRepository(), JobAuditRepository(), redis_client
            )

            doc_repo = DocumentRepository()
            version = await doc_repo.get_version(version_id, session)

            if not version:
                await job_service.record_step_error(
                    job_id, "extraction", self.request.id, "VERSION_NOT_FOUND", "Version not found", True, session
                )
                return

            await job_service.start_step(job_id, "extraction", self.request.id, session)
            start_time = datetime.now(UTC)

            try:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"File not found: {file_path}")

                with open(file_path, "rb") as f:
                    extractor = UnstructuredExtractor(
                        use_ocr=version.requires_ocr,
                        ocr_languages=version.ocr_languages or ["eng"]
                    )

                    result = extractor.extract(f)

                # Normalize and detect
                normalized = normalize_text(result.raw_text)
                detected_lang = detect_language(normalized)

                # Save extracted text
                extracted_path = f"{file_path}.extracted.txt"
                with open(extracted_path, "w", encoding="utf-8") as f:
                    f.write(normalized)

                version.extracted_text_path = extracted_path
                # Assuming document is eager loaded or we update document language
                # doc_repo doesn't have an update method directly, but session.flush() works

                await job_service.complete_step(
                    job_id,
                    "extraction",
                    self.request.id,
                    {
                        "language": detected_lang,
                        "ocr_used": version.requires_ocr,
                        "char_count": len(normalized)
                    },
                    session
                )

                duration = (datetime.now(UTC) - start_time).total_seconds()
                STEP_DURATION_SECONDS.labels(step_name="extraction", status="success").observe(duration)

            except Exception as e:
                logger.exception("Extraction failed", job_id=str(job_id))
                await job_service.record_step_error(
                    job_id, "extraction", self.request.id, "EXTRACTION_FAILED", str(e), False, session
                )
                duration = (datetime.now(UTC) - start_time).total_seconds()
                STEP_DURATION_SECONDS.labels(step_name="extraction", status="failure").observe(duration)
                raise self.retry(exc=e, countdown=60)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
