"""Celery Ingestion Worker (`process_document_job`).

Runs asynchronous document ingestion tasks on the dedicated `ingestion` queue.
Executes extraction, OCR, normalization, manifest generation, and contract verification,
enforcing strict retry policy based on error severity (`RECOVERABLE` vs `FATAL`).
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.core.config import get_settings
from backend.document.events import (EVENT_DOCUMENT_FAILED,
                                     EVENT_DOCUMENT_PROCESSED,
                                     EVENT_DOCUMENT_VALIDATED,
                                     EVENT_METADATA_EXTRACTED,
                                     EVENT_OCR_COMPLETED, EVENT_TEXT_EXTRACTED,
                                     create_domain_event)
from backend.document.extractors import create_default_registry, normalize_text
from backend.document.models import DocumentEventLog
from backend.document.ocr import OCRPipeline
from backend.document.repositories import (DocumentEventRepository,
                                           DocumentRepository, JobRepository)
from backend.document.schemas import DocumentManifestDTO, StageMetricDTO
from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode, ErrorSeverity,
                                             get_error_severity)
from backend.document.storage import (DocumentProcessingContract,
                                      LocalStorageProvider, get_versioned_path)
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, queue="ingestion", max_retries=3, acks_late=True)
def process_document_job(self: Any, job_id: str) -> dict[str, Any]:
    """Background Celery task executing the document processing pipeline.

    Args:
        job_id: String UUID of the ProcessingJob record.

    Returns:
        Dictionary summary of the execution outcome.
    """
    return asyncio.run(_async_process_job(self, job_id))


async def _async_process_job(task_instance: Any, job_id: str) -> dict[str, Any]:
    """Async wrapper that delegates to _do_process_job."""
    from backend.database.engine import get_session_factory
    session_factory = get_session_factory()
    return await _do_process_job(task_instance, job_id, session_factory)


async def _do_process_job(task_instance: Any, job_id: str, session_factory: Any) -> dict[str, Any]:
    """Async inner implementation for `process_document_job`."""

    doc_repo = DocumentRepository()
    job_repo = JobRepository()
    event_repo = DocumentEventRepository()
    storage = LocalStorageProvider()
    registry = create_default_registry()
    ocr_pipeline = OCRPipeline()

    stage_metrics: list[StageMetricDTO] = []

    async with session_factory() as session:
        try:
            job_uuid = uuid.UUID(job_id)
            job = await job_repo.get_by_id(job_uuid, session)
            if not job or job.status in {"COMPLETED", "is_deleted"}:
                return {"status": "skipped", "reason": "Job missing or completed"}

            if not job.version_id:
                raise DocumentDomainException(
                    code=DocumentErrorCode.SYS_001,
                    message="Job is missing target version_id.",
                )

            doc = await doc_repo.get_by_id_with_versions(
                job.document_id, str(job.document_id), session
            )
            if not doc:
                # Fallback without tenant check if tenant_id is unknown to worker initially
                from sqlalchemy import select
                from backend.document.models import Document
                
                tenant_id_stmt = select(Document.tenant_id).where(Document.id == job.document_id)
                actual_tenant_id = await session.scalar(tenant_id_stmt)
                
                if not actual_tenant_id:
                    raise DocumentDomainException(
                        code=DocumentErrorCode.SYS_001,
                        message="Target document or version missing.",
                    )
                doc = await doc_repo.get_by_id_with_versions(
                    job.document_id, actual_tenant_id, session
                )

            if not doc or not doc.versions:
                raise DocumentDomainException(
                    code=DocumentErrorCode.SYS_001,
                    message="Document aggregate root missing or has zero versions.",
                )

            version = next(
                (v for v in doc.versions if v.id == job.version_id), doc.versions[0]
            )
            if not version.storage_object:
                raise DocumentDomainException(
                    code=DocumentErrorCode.STORE_002,
                    message="StorageObject link missing on version record.",
                )

            tenant_id = doc.tenant_id

            # ── Stage 1: Validation ──────────────────────────────────────────────
            t0 = time.perf_counter()
            doc.status = "VALIDATING"
            job.current_step = "validation"
            job.status = "VALIDATING"
            await session.commit()

            stream = await storage.get_stream(version.storage_object.object_key)
            val_duration = (time.perf_counter() - t0) * 1000.0
            stage_metrics.append(
                StageMetricDTO(
                    stage="validation",
                    duration_ms=round(val_duration, 2),
                    status="COMPLETED",
                )
            )

            # Log validation event
            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_VALIDATED,
                tenant_id=tenant_id,
                document_id=doc.id,
                job_id=job.id,
                data={
                    "object_key": version.storage_object.object_key,
                    "duration_ms": round(val_duration, 2),
                },
            )
            await event_repo.append_event(
                DocumentEventLog(
                    document_id=doc.id,
                    job_id=job.id,
                    event_type=EVENT_DOCUMENT_VALIDATED,
                    payload=payload.model_dump(mode="json"),
                    triggered_by="celery_worker",
                ),
                session,
            )
            await session.commit()

            # ── Stage 2: Extraction ──────────────────────────────────────────────
            t1 = time.perf_counter()
            doc.status = "EXTRACTING"
            job.current_step = "extraction"
            job.status = "EXTRACTING"
            await session.commit()

            extractor = registry.get_extractor(
                mime_type=version.storage_object.mime_type,
                extension=(
                    "." + doc.filename.split(".")[-1] if "." in doc.filename else ".txt"
                ),
            )
            extracted = await extractor.extract(
                stream, doc.filename, version.storage_object.mime_type
            )
            ext_duration = (time.perf_counter() - t1) * 1000.0
            stage_metrics.append(
                StageMetricDTO(
                    stage="extraction",
                    duration_ms=round(ext_duration, 2),
                    status="COMPLETED",
                )
            )

            # Log metadata and text extracted events
            for ev_type in (EVENT_METADATA_EXTRACTED, EVENT_TEXT_EXTRACTED):
                ev_payload = create_domain_event(
                    event_type=ev_type,
                    tenant_id=tenant_id,
                    document_id=doc.id,
                    job_id=job.id,
                    data={
                        "word_count": extracted.word_count,
                        "page_count": extracted.page_count,
                    },
                )
                await event_repo.append_event(
                    DocumentEventLog(
                        document_id=doc.id,
                        job_id=job.id,
                        event_type=ev_type,
                        payload=ev_payload.model_dump(mode="json"),
                        triggered_by="celery_worker",
                    ),
                    session,
                )
            await session.commit()

            # ── Stage 3: OCR Fallback (if required) ──────────────────────────────
            if extracted.needs_ocr:
                t2 = time.perf_counter()
                doc.status = "OCR"
                job.current_step = "ocr"
                await session.commit()

                stream.seek(0)
                ocr_res = await ocr_pipeline.execute(stream, doc.filename)
                extracted.text = ocr_res.text
                extracted.word_count = ocr_res.word_count
                extracted.page_count = ocr_res.page_count
                extracted.metadata["ocr_engine_used"] = ocr_res.engine_used

                ocr_duration = (time.perf_counter() - t2) * 1000.0
                stage_metrics.append(
                    StageMetricDTO(
                        stage="ocr",
                        duration_ms=round(ocr_duration, 2),
                        status="COMPLETED",
                    )
                )

                ocr_payload = create_domain_event(
                    event_type=EVENT_OCR_COMPLETED,
                    tenant_id=tenant_id,
                    document_id=doc.id,
                    job_id=job.id,
                    data={
                        "engine": ocr_res.engine_used,
                        "confidence": ocr_res.confidence,
                    },
                )
                await event_repo.append_event(
                    DocumentEventLog(
                        document_id=doc.id,
                        job_id=job.id,
                        event_type=EVENT_OCR_COMPLETED,
                        payload=ocr_payload.model_dump(mode="json"),
                        triggered_by="celery_worker",
                    ),
                    session,
                )
                await session.commit()

            # ── Stage 4: Normalization & Storage Artifacts ───────────────────────
            job.current_step = "storage"
            await session.commit()

            clean_text = normalize_text(extracted.text)
            norm_key = get_versioned_path(
                tenant_id=tenant_id,
                document_id=doc.id,
                version_number=version.version_number,
                category="normalized",
                filename="text.txt",
            )
            await storage.save_bytes(clean_text.encode("utf-8"), norm_key)
            version.extracted_text_path = norm_key

            ext_meta_key = get_versioned_path(
                tenant_id=tenant_id,
                document_id=doc.id,
                version_number=version.version_number,
                category="metadata",
                filename="extraction.json",
            )
            await storage.save_json(extracted.metadata, ext_meta_key)
            version.metadata_json = extracted.metadata
            await session.commit()

            # ── Stage 5: Canonical Manifest Generation ───────────────────────────
            doc.status = "MANIFEST_GENERATING"
            job.current_step = "manifest"
            await session.commit()

            manifest_dto = DocumentManifestDTO(
                manifest_version="1.0.0",
                document_id=doc.id,
                version_id=version.id,
                version_number=version.version_number,
                tenant_id=tenant_id,
                owner_user_id=doc.owner_user_id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                mime_type=version.storage_object.mime_type,
                file_size_bytes=version.storage_object.file_size_bytes,
                checksum_sha256=version.storage_object.checksum_sha256,
                storage_provider=version.storage_object.provider,
                original_storage_key=version.storage_object.object_key,
                normalized_text_path=norm_key,
                metadata_json_path=ext_meta_key,
                page_count=extracted.page_count,
                word_count=extracted.word_count,
                language=extracted.language,
                encoding="utf-8",
                stage_metrics=stage_metrics,
                extraction_metadata=extracted.metadata,
                created_at=datetime.now(UTC).isoformat(),
            )
            manifest_key = get_versioned_path(
                tenant_id=tenant_id,
                document_id=doc.id,
                version_number=version.version_number,
                category="metadata",
                filename="manifest.json",
            )
            await storage.save_json(manifest_dto.model_dump(mode="json"), manifest_key)

            # ── Stage 6: Contract Verification & Final Transition ────────────────
            await DocumentProcessingContract.verify(doc, version, storage)

            doc.status = "PROCESSED"
            doc.word_count = extracted.word_count
            doc.page_count = extracted.page_count
            doc.language = extracted.language

            job.status = "COMPLETED"
            job.current_step = "completed"
            job.completed_at = datetime.now(UTC)

            # Emit DocumentProcessed event
            proc_payload = create_domain_event(
                event_type=EVENT_DOCUMENT_PROCESSED,
                tenant_id=tenant_id,
                document_id=doc.id,
                job_id=job.id,
                data={"manifest_key": manifest_key, "word_count": doc.word_count},
            )
            await event_repo.append_event(
                DocumentEventLog(
                    document_id=doc.id,
                    job_id=job.id,
                    event_type=EVENT_DOCUMENT_PROCESSED,
                    payload=proc_payload.model_dump(mode="json"),
                    triggered_by="celery_worker",
                ),
                session,
            )
            await session.commit()
            
            # Publish event in process to trigger next pipeline stage
            from backend.core.events.dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            await dispatcher.publish(proc_payload)

            logger.info(
                "Document processing completed successfully",
                document_id=str(doc.id),
                job_id=job_id,
            )
            return {
                "status": "success",
                "document_id": str(doc.id),
                "word_count": doc.word_count,
            }

        except Exception as e:
            await session.rollback()
            code_str = (
                e.code
                if isinstance(e, DocumentDomainException)
                else DocumentErrorCode.SYS_002
            )
            severity = (
                e.severity
                if isinstance(e, DocumentDomainException)
                else get_error_severity(code_str)
            )

            # Load job within new session/transaction for error update
            job_uuid = uuid.UUID(job_id)
            job = await job_repo.get_by_id(job_uuid, session)
            if job:
                doc = await doc_repo.get_by_id(
                    job.document_id, str(job.document_id), session
                )
                if not doc:
                    v = (
                        await doc_repo.get_version_by_id(job.version_id, session)
                        if job.version_id
                        else None
                    )
                    if v:
                        doc = await doc_repo.get_by_id(
                            job.document_id, actual_tenant_id, session
                        )

                if (
                    severity == ErrorSeverity.RECOVERABLE
                    and job.retry_count < job.max_retries
                ):
                    job.retry_count += 1
                    job.error_code = str(code_str)
                    job.error_message = str(e)
                    job.status = "RETRYING"
                    await session.commit()

                    # Trigger Celery exponential backoff retry
                    countdown = int(2**job.retry_count)
                    logger.warning(
                        "Recoverable error during ingestion; retrying",
                        job_id=job_id,
                        retry_count=job.retry_count,
                        countdown=countdown,
                        error=str(e),
                    )
                    raise task_instance.retry(exc=e, countdown=countdown) from e

                # Fatal or retries exhausted
                job.status = "FAILED"
                job.error_code = str(code_str)
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)

                if doc:
                    doc.status = "FAILED"
                    fail_payload = create_domain_event(
                        event_type=EVENT_DOCUMENT_FAILED,
                        tenant_id=doc.tenant_id,
                        document_id=doc.id,
                        job_id=job.id,
                        data={
                            "error_code": str(code_str),
                            "error_message": str(e),
                            "severity": str(severity),
                        },
                    )
                    await event_repo.append_event(
                        DocumentEventLog(
                            document_id=doc.id,
                            job_id=job.id,
                            event_type=EVENT_DOCUMENT_FAILED,
                            payload=fail_payload.model_dump(mode="json"),
                            triggered_by="celery_worker",
                        ),
                        session,
                    )
                await session.commit()

            logger.error(
                "Document ingestion job failed permanently",
                job_id=job_id,
                error_code=str(code_str),
                error=str(e),
            )
            return {"status": "failed", "error_code": str(code_str), "message": str(e)}
