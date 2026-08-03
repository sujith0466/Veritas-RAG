from backend.document.models.status import DocumentStatus

"""Document Domain Service (`DocumentService`).

Orchestrates synchronous file upload processing, validation screening, physical artifact storage,
database entity persistence, event emitting, and asynchronous Celery worker task dispatch (`ADR-005`).
"""

import math
from typing import BinaryIO
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.cache.locks import acquire_lock
from backend.document.schemas.errors import DocumentDomainException
from backend.document.events import (
    EVENT_DOCUMENT_UPLOADED,
    EVENT_DOCUMENT_ARCHIVED,
    EVENT_DOCUMENT_RESTORED,
    EVENT_DOCUMENT_VERSION_CREATED,
    EVENT_DOCUMENT_ROLLED_BACK,
    create_domain_event,
)
from backend.document.models import (
    Document,
    DocumentEventLog,
    DocumentVersion,
    ProcessingJob,
    StorageObject,
)
from backend.document.repositories import (
    DocumentEventRepository,
    DocumentRepository,
    JobRepository,
    StorageObjectRepository,
)
from backend.document.schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentManifestDTO,
    DocumentResponse,
    DocumentVersionDTO,
    ProcessingStatusResponse,
)
from backend.document.storage import LocalStorageProvider, StorageProvider, get_versioned_path
from backend.document.validators import ValidationPipeline, check_duplicate_content


class DocumentService:
    """Orchestrates document lifecycle management and ingestion workflow."""

    def __init__(
        self,
        storage_provider: StorageProvider | None = None,
        doc_repo: DocumentRepository | None = None,
        job_repo: JobRepository | None = None,
        storage_repo: StorageObjectRepository | None = None,
        event_repo: DocumentEventRepository | None = None,
        validator_pipeline: ValidationPipeline | None = None,
    ) -> None:
        self.storage = storage_provider or LocalStorageProvider()
        self.doc_repo = doc_repo or DocumentRepository()
        self.job_repo = job_repo or JobRepository()
        self.storage_repo = storage_repo or StorageObjectRepository()
        self.event_repo = event_repo or DocumentEventRepository()
        self.validator = validator_pipeline or ValidationPipeline()

    async def upload_document(
        self,
        stream: BinaryIO,
        filename: str,
        declared_mime: str,
        tenant_id: str,
        owner_user_id: uuid.UUID | None,
        session: AsyncSession,
        relative_path: str | None = None,
    ) -> tuple[Document, DocumentVersion, ProcessingJob]:
        """Accept file upload, validate safety/extension, store original artifact, and dispatch background job."""
        # 1. Run preliminary validation (size, sanitization, extension/MIME/magic, virus scan, sha256)
        validation_result = await self.validator.validate(
            stream=stream,
            original_filename=filename,
            declared_mime=declared_mime,
        )

        # 2. Check for duplicate content within tenant namespace
        await check_duplicate_content(
            content_hash=validation_result.content_hash,
            tenant_id=tenant_id,
            session=session,
            reject_duplicates=False,  # Can set to True per strict quota policy; currently allowed as distinct version/doc
        )

        # 3. Generate IDs and canonical storage key
        document_id = uuid.uuid4()
        version_number = 1
        original_key = get_versioned_path(
            tenant_id=tenant_id,
            document_id=document_id,
            version_number=version_number,
            category="original",
            filename=validation_result.sanitized_filename,
        )

        # 4. Save physical binary artifact
        storage_dto = await self.storage.save_stream(stream, original_key)

        # 5. Persist StorageObject metadata entity
        storage_obj = StorageObject(
            provider=storage_dto.provider,
            bucket_or_container=storage_dto.bucket_or_container,
            object_key=storage_dto.object_key,
            file_size_bytes=storage_dto.file_size_bytes,
            mime_type=validation_result.mime_type,
            checksum_sha256=storage_dto.checksum_sha256,
        )
        storage_obj = await self.storage_repo.create(storage_obj, session)

        # 6. Persist Document aggregate root
        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            filename=validation_result.sanitized_filename,
            original_filename=validation_result.original_filename,
            relative_path=relative_path,
            status=DocumentStatus.UPLOADED,
            word_count=0,
            page_count=0,
        )
        document = await self.doc_repo.create(document, session)

        # 7. Persist DocumentVersion
        version = DocumentVersion(
            document_id=document.id,
            version_number=version_number,
            storage_object_id=storage_obj.id,
            content_hash=storage_dto.checksum_sha256,
        )
        version = await self.doc_repo.add_version(version, session)

        document.latest_version_id = version.id
        await session.flush()

        # 8. Persist ProcessingJob tracking record
        job = ProcessingJob(
            document_id=document.id,
            version_id=version.id,
            status=DocumentStatus.PENDING,
            current_step="upload",
            retry_count=0,
            max_retries=3,
        )
        job = await self.job_repo.create(job, session)

        # 9. Emit versioned domain event (`DocumentUploaded`)
        payload = create_domain_event(
            event_type=EVENT_DOCUMENT_UPLOADED,
            tenant_id=tenant_id,
            document_id=document.id,
            job_id=job.id,
            data={
                "filename": document.filename,
                "file_size_bytes": storage_dto.file_size_bytes,
                "mime_type": validation_result.mime_type,
                "checksum_sha256": storage_dto.checksum_sha256,
            },
        )
        event_log = DocumentEventLog(
            document_id=document.id,
            job_id=job.id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            payload=payload.model_dump(mode="json"),
            triggered_by="upload_api",
        )
        await self.event_repo.append_event(event_log, session)

        # Commit transaction before enqueuing asynchronous Celery task
        await session.commit()

        # 10. Dispatch Celery ingestion task
        try:
            # Import inside method to avoid circular imports during startup
            from backend.document.workers.ingestion import process_document_job

            process_document_job.apply_async(args=[str(job.id)], queue="ingestion")
        except Exception as e:
            # If broker dispatch fails, log warning/error without failing the upload record
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error("Failed to dispatch process_document_job", error=str(e), job_id=str(job.id))
            pass

        return document, version, job

    async def get_status(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> ProcessingStatusResponse | None:
        """Get current processing status and progress percentage for a document."""
        doc = await self.doc_repo.get_by_id(document_id, tenant_id, session)
        if not doc:
            return None

        job = await self.job_repo.get_by_document_id(document_id, session)

        # Monotonic progress calculation based on authoritative Document.status
        status_map = {
            "UPLOADED": 10,
            "VALIDATING": 20,
            "EXTRACTING": 30,
            "OCR": 40,
            "MANIFEST_GENERATING": 45,
            "PROCESSED": 50,
            "CHUNKING": 65,
            "EMBEDDING": 80,
            "VECTOR_SYNC": 90,
            "READY": 100,
            "FAILED": 100
        }

        progress = status_map.get(doc.status, 15)

        # If it's still UPLOADED, use job progress if available, but cap it so it never exceeds PROCESSED
        if doc.status == DocumentStatus.UPLOADED and job:
            job_step_progress = {
                "upload": 10,
                "validation": 20,
                "extraction": 30,
                "ocr": 40,
                "manifest": 45,
            }
            job_prog = job_step_progress.get(job.current_step.lower(), 10)
            progress = max(progress, job_prog)

        return ProcessingStatusResponse(
            document_id=doc.id,
            status=doc.status,
            current_step=job.current_step if job else doc.status.lower(),
            progress_percent=progress,
            retry_count=job.retry_count if job else 0,
            error_code=job.error_code if job else None,
            error_message=job.error_message if job else None,
            updated_at=doc.updated_at,
        )

    async def get_document_detail(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> DocumentDetailResponse | None:
        """Fetch complete document details, version history, and manifest if processed."""
        doc = await self.doc_repo.get_by_id_with_versions(
            document_id, tenant_id, session
        )
        if not doc:
            return None

        versions_dto = [DocumentVersionDTO.model_validate(v) for v in doc.versions]

        manifest_dto: DocumentManifestDTO | None = None
        if doc.status == DocumentStatus.PROCESSED and doc.versions:
            latest_version = max(doc.versions, key=lambda v: v.version_number)
            manifest_key = get_versioned_path(
                tenant_id=doc.tenant_id,
                document_id=doc.id,
                version_number=latest_version.version_number,
                category="metadata",
                filename="manifest.json",
            )
            if await self.storage.object_exists(manifest_key):
                try:
                    manifest_data = await self.storage.get_json(manifest_key)
                    manifest_dto = DocumentManifestDTO.model_validate(manifest_data)
                except Exception:
                    pass

        return DocumentDetailResponse(
            id=doc.id,
            tenant_id=doc.tenant_id,
            owner_user_id=doc.owner_user_id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            relative_path=doc.relative_path,
            status=doc.status,
            latest_version_id=doc.latest_version_id,
            word_count=doc.word_count,
            page_count=doc.page_count,
            language=doc.language,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            versions=versions_dto,
            manifest=manifest_dto,
        )

    async def list_documents(
        self,
        tenant_id: str,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> DocumentListResponse:
        """List documents within a tenant namespace with pagination."""
        items, total = await self.doc_repo.list_documents(
            tenant_id, session, page, page_size, status
        )
        items_dto = [DocumentResponse.model_validate(item) for item in items]
        pages = math.ceil(total / page_size) if page_size > 0 else 1

        return DocumentListResponse(
            items=items_dto,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def delete_document(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> bool:
        """Soft-delete a document and remove its physical artifacts from storage."""
        doc = await self.doc_repo.get_by_id_with_versions(
            document_id, tenant_id, session
        )
        if not doc:
            return False

        # Soft delete in database
        success = await self.doc_repo.delete(document_id, tenant_id, session)
        if not success:
            return False

        await session.commit()

        # Delete physical artifacts from storage prefix (`documents/{tenant_id}/{document_id}`)
        prefix = f"documents/{tenant_id}/{document_id}"
        await self.storage.delete_prefix(prefix)

        return True

    async def archive_document(
        self, document_id: uuid.UUID, tenant_id: str, user_id: uuid.UUID | None, session: AsyncSession
    ) -> Document:
        """Archive a document and remove its vectors from Qdrant."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.doc_repo.get_by_id(document_id, tenant_id, session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found")
            if doc.status in (DocumentStatus.ARCHIVED, DocumentStatus.DELETED):
                raise DocumentDomainException("VAL_001", f"Cannot archive document in status {doc.status}")

            doc = await self.doc_repo.archive_document(document_id, tenant_id, user_id, session)

            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_ARCHIVED,
                tenant_id=tenant_id,
                document_id=document_id,
            )
            event_log = DocumentEventLog(
                document_id=document_id,
                event_type=EVENT_DOCUMENT_ARCHIVED,
                payload=payload.model_dump(mode="json"),
                triggered_by="archive_api",
            )
            await self.event_repo.append_event(event_log, session)
            await session.commit()

            try:
                from backend.document.workers.archive import remove_archived_document_vectors_job
                remove_archived_document_vectors_job.apply_async(args=[str(document_id), tenant_id], queue="ingestion")
            except Exception as e:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.error("Failed to dispatch remove_archived_document_vectors_job", error=str(e), doc_id=str(document_id))

            return doc

    async def restore_document(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> Document:
        """Restore an archived document and re-sync its vectors to Qdrant."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.doc_repo.restore_document(document_id, tenant_id, session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found or parent folder is soft-deleted")

            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_RESTORED,
                tenant_id=tenant_id,
                document_id=document_id,
            )
            event_log = DocumentEventLog(
                document_id=document_id,
                event_type=EVENT_DOCUMENT_RESTORED,
                payload=payload.model_dump(mode="json"),
                triggered_by="restore_api",
            )
            await self.event_repo.append_event(event_log, session)
            await session.commit()

            try:
                from backend.document.workers.archive import restore_archived_document_vectors_job
                restore_archived_document_vectors_job.apply_async(args=[str(document_id), str(doc.latest_version_id), tenant_id], queue="ingestion")
            except Exception as e:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.error("Failed to dispatch restore_archived_document_vectors_job", error=str(e), doc_id=str(document_id))

            return doc

    async def upload_new_version(
        self,
        document_id: uuid.UUID,
        stream: BinaryIO,
        filename: str,
        declared_mime: str,
        tenant_id: str,
        owner_user_id: uuid.UUID | None,
        session: AsyncSession,
    ) -> tuple[Document, DocumentVersion, ProcessingJob]:
        """Upload a new immutable version of a document."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found")
            if doc.status in (DocumentStatus.ARCHIVED, DocumentStatus.DELETED):
                raise DocumentDomainException("VAL_001", "Cannot version an archived or deleted document")

            # Validation
            validation_result = await self.validator.validate(
                stream=stream,
                original_filename=filename,
                declared_mime=declared_mime,
            )

            # Determine new version number
            latest_version_num = max(v.version_number for v in doc.versions) if doc.versions else 0
            new_version_num = latest_version_num + 1

            original_key = get_versioned_path(
                tenant_id=tenant_id,
                document_id=document_id,
                version_number=new_version_num,
                category="original",
                filename=validation_result.sanitized_filename,
            )

            storage_dto = await self.storage.save_stream(stream, original_key)

            storage_obj = StorageObject(
                provider=storage_dto.provider,
                bucket_or_container=storage_dto.bucket_or_container,
                object_key=storage_dto.object_key,
                file_size_bytes=storage_dto.file_size_bytes,
                mime_type=validation_result.mime_type,
                checksum_sha256=storage_dto.checksum_sha256,
            )
            storage_obj = await self.storage_repo.create(storage_obj, session)

            version = DocumentVersion(
                document_id=doc.id,
                version_number=new_version_num,
                storage_object_id=storage_obj.id,
                content_hash=storage_dto.checksum_sha256,
                is_active_vector=True,
            )
            version = await self.doc_repo.add_version(version, session)

            # Deactivate older vectors in DB flag
            await self.doc_repo.set_active_version(doc.id, version.id, session)

            doc.latest_version_id = version.id
            doc.status = DocumentStatus.UPLOADED
            await session.flush()

            job = ProcessingJob(
                document_id=doc.id,
                version_id=version.id,
                status=DocumentStatus.PENDING,
                current_step="upload",
                retry_count=0,
                max_retries=3,
            )
            job = await self.job_repo.create(job, session)

            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_VERSION_CREATED,
                tenant_id=tenant_id,
                document_id=doc.id,
                job_id=job.id,
                data={
                    "version_number": new_version_num,
                    "filename": doc.filename,
                    "file_size_bytes": storage_dto.file_size_bytes,
                },
            )
            event_log = DocumentEventLog(
                document_id=doc.id,
                job_id=job.id,
                event_type=EVENT_DOCUMENT_VERSION_CREATED,
                payload=payload.model_dump(mode="json"),
                triggered_by="version_api",
            )
            await self.event_repo.append_event(event_log, session)
            await session.commit()

            try:
                from backend.document.workers.ingestion import process_document_job
                process_document_job.apply_async(args=[str(job.id)], queue="ingestion")
            except Exception as e:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.error("Failed to dispatch process_document_job for new version", error=str(e), job_id=str(job.id))

            return doc, version, job

    async def rollback_to_version(
        self, document_id: uuid.UUID, target_version_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> tuple[Document, DocumentVersion, ProcessingJob]:
        """Rollback to an older version by cloning it as the newest version."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found")
            if doc.status in (DocumentStatus.ARCHIVED, DocumentStatus.DELETED):
                raise DocumentDomainException("VAL_001", "Cannot rollback an archived or deleted document")

            target_version = next((v for v in doc.versions if v.id == target_version_id), None)
            if not target_version:
                raise DocumentDomainException("STORE_002", "Target version not found")

            latest_version_num = max(v.version_number for v in doc.versions) if doc.versions else 0
            new_version_num = latest_version_num + 1

            version = DocumentVersion(
                document_id=doc.id,
                version_number=new_version_num,
                storage_object_id=target_version.storage_object_id,
                content_hash=target_version.content_hash,
                is_active_vector=True,
            )
            version = await self.doc_repo.add_version(version, session)

            await self.doc_repo.set_active_version(doc.id, version.id, session)

            doc.latest_version_id = version.id
            doc.status = DocumentStatus.UPLOADED
            await session.flush()

            job = ProcessingJob(
                document_id=doc.id,
                version_id=version.id,
                status=DocumentStatus.PENDING,
                current_step="upload",
                retry_count=0,
                max_retries=3,
            )
            job = await self.job_repo.create(job, session)

            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_ROLLED_BACK,
                tenant_id=tenant_id,
                document_id=doc.id,
                job_id=job.id,
                data={
                    "version_number": new_version_num,
                    "target_version_id": str(target_version_id),
                },
            )
            event_log = DocumentEventLog(
                document_id=doc.id,
                job_id=job.id,
                event_type=EVENT_DOCUMENT_ROLLED_BACK,
                payload=payload.model_dump(mode="json"),
                triggered_by="rollback_api",
            )
            await self.event_repo.append_event(event_log, session)
            await session.commit()

            try:
                from backend.document.workers.ingestion import process_document_job
                process_document_job.apply_async(args=[str(job.id)], queue="ingestion")
            except Exception as e:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.error("Failed to dispatch process_document_job for rollback", error=str(e), job_id=str(job.id))

            return doc, version, job
