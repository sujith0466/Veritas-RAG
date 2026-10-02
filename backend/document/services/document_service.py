"""Document Domain Service (`DocumentService`).

Orchestrates synchronous file upload processing, validation screening, physical artifact storage,
database entity persistence, event emitting, and asynchronous Celery worker task dispatch (`ADR-005`).
"""

from __future__ import annotations

from datetime import UTC, datetime
import math
import posixpath
from typing import BinaryIO
import urllib.parse
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.cache.locks import acquire_lock
from backend.document.events import (
    EVENT_DOCUMENT_ARCHIVED,
    EVENT_DOCUMENT_DELETED,
    EVENT_DOCUMENT_REINGESTED,
    EVENT_DOCUMENT_RESTORED,
    EVENT_DOCUMENT_RETRIED,
    EVENT_DOCUMENT_ROLLED_BACK,
    EVENT_DOCUMENT_UPLOADED,
    EVENT_DOCUMENT_VERSION_CREATED,
    create_domain_event,
)
from backend.document.models import (
    Document,
    DocumentEventLog,
    DocumentVersion,
    ProcessingJob,
    StorageObject,
)
from backend.document.models.job import DispatchState
from backend.document.models.status import DocumentStatus
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
from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode
from backend.document.services.job_dispatcher import JobDispatcher
from backend.document.services.url_security import (
    SSRFSafeUrlValidator,
    SSRFSecurityException,
    normalize_url_identity,
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

        # 10. Resilient dispatch of Celery ingestion task
        from backend.document.services.job_dispatcher import JobDispatcher
        await JobDispatcher.dispatch_job(job, session=session, queue="ingestion")
        await session.commit()

        return document, version, job

    async def _create_website_document(
        self,
        normalized_url: str,
        tenant_id: str,
        owner_user_id: uuid.UUID | None,
        session: AsyncSession,
        user_metadata: dict | None = None,
    ) -> tuple[Document, DocumentVersion, ProcessingJob]:
        """Helper to create initial Document, StorageObject, DocumentVersion and ProcessingJob."""
        parsed = urllib.parse.urlsplit(normalized_url)
        path = parsed.path.strip("/")
        if path:
            base = posixpath.basename(path)
            derived_name = base if "." in base else f"{base}.html"
        else:
            host_clean = (parsed.hostname or "website").replace(".", "_")
            derived_name = f"{host_clean}.html"

        document_id = uuid.uuid4()
        version_number = 1
        storage_key = get_versioned_path(
            tenant_id=tenant_id,
            document_id=document_id,
            version_number=version_number,
            category="original",
            filename="snapshot.html",
        )

        storage_obj = StorageObject(
            provider="local",
            bucket_or_container="raguard-storage",
            object_key=storage_key,
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        storage_obj = await self.storage_repo.create(storage_obj, session)

        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            filename=derived_name,
            original_filename=normalized_url,
            source_type="website",
            source_url=normalized_url,
            status=DocumentStatus.PENDING,
            word_count=0,
            page_count=0,
            user_metadata=user_metadata or {},
        )
        document = await self.doc_repo.create(document, session)

        version = DocumentVersion(
            document_id=document.id,
            version_number=version_number,
            storage_object_id=storage_obj.id,
            content_hash="pending_fetch",
            is_active_vector=True,
        )
        version = await self.doc_repo.add_version(version, session)
        document.latest_version_id = version.id
        await session.flush()

        job = ProcessingJob(
            document_id=document.id,
            version_id=version.id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )
        job = await self.job_repo.create(job, session)

        payload = create_domain_event(
            event_type=EVENT_DOCUMENT_UPLOADED,
            tenant_id=tenant_id,
            document_id=document.id,
            job_id=job.id,
            data={
                "filename": document.filename,
                "source_type": "website",
                "source_url": normalized_url,
                "status": DocumentStatus.PENDING,
            },
        )
        event_log = DocumentEventLog(
            document_id=document.id,
            job_id=job.id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            payload=payload.model_dump(mode="json"),
            triggered_by="url_api",
        )
        await self.event_repo.append_event(event_log, session)
        await session.commit()

        await JobDispatcher.dispatch_job(job, session=session, queue="ingestion")
        await session.commit()
        return document, version, job

    async def ingest_url(
        self,
        url: str,
        tenant_id: str,
        owner_user_id: uuid.UUID | None,
        session: AsyncSession,
        user_metadata: dict | None = None,
    ) -> tuple[Document, DocumentVersion, ProcessingJob | None, bool]:
        """Ingest a remote website URL as a Knowledge Source Document."""
        # 1. Normalize URL identity
        try:
            normalized_url = normalize_url_identity(url)
        except SSRFSecurityException as e:
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_002,
                message=f"Invalid URL syntax: {e.message}",
                detail=e.detail,
            ) from e

        # 2. Validate URL safety & resolve destination (SSRF check)
        try:
            await SSRFSafeUrlValidator.validate_destination(normalized_url)
        except SSRFSecurityException as ssrf_err:
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_002,
                message=f"SSRF validation rejected URL: {ssrf_err.message}",
                detail=ssrf_err.detail,
            ) from ssrf_err

        # 3. Check for existing website Document within tenant namespace
        existing_doc = await self.doc_repo.get_by_source_url(normalized_url, tenant_id, session)
        if existing_doc:
            active_statuses = {
                DocumentStatus.PENDING.value,
                DocumentStatus.UPLOADED.value,
                DocumentStatus.FETCHING.value,
                DocumentStatus.VALIDATING.value,
                DocumentStatus.EXTRACTING.value,
                DocumentStatus.OCR.value,
                DocumentStatus.MANIFEST_GENERATING.value,
                DocumentStatus.PROCESSED.value,
                DocumentStatus.CHUNKING.value,
                DocumentStatus.CHUNKED.value,
                DocumentStatus.EMBEDDING.value,
                DocumentStatus.EMBEDDED.value,
                DocumentStatus.VECTOR_SYNC.value,
            }
            if existing_doc.status in active_statuses:
                active_job = await self.job_repo.get_by_document_id(existing_doc.id, session)
                v = await self.doc_repo.get_version_by_id(existing_doc.latest_version_id, session) if existing_doc.latest_version_id else None
                return existing_doc, v or existing_doc.versions[0], active_job, True

            if existing_doc.status == DocumentStatus.READY.value:
                v = await self.doc_repo.get_version_by_id(existing_doc.latest_version_id, session) if existing_doc.latest_version_id else None
                return existing_doc, v or existing_doc.versions[0], None, True

            # If FAILED, trigger re-processing on existing document
            job = ProcessingJob(
                document_id=existing_doc.id,
                version_id=existing_doc.latest_version_id,
                status=DocumentStatus.PENDING,
                current_step="fetch",
                retry_count=0,
                max_retries=3,
            )
            job = await self.job_repo.create(job, session)
            existing_doc.status = DocumentStatus.PENDING
            await session.commit()
            await JobDispatcher.dispatch_job(job, session=session, queue="ingestion")
            await session.commit()
            v = await self.doc_repo.get_version_by_id(existing_doc.latest_version_id, session) if existing_doc.latest_version_id else None
            return existing_doc, v or existing_doc.versions[0], job, True

        # 4. First ingestion path
        doc, ver, job = await self._create_website_document(
            normalized_url=normalized_url,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session=session,
            user_metadata=user_metadata,
        )
        return doc, ver, job, False

    async def refresh_url(
        self,
        document_id: uuid.UUID,
        tenant_id: str,
        owner_user_id: uuid.UUID | None,
        session: AsyncSession,
    ) -> tuple[Document, DocumentVersion, ProcessingJob]:
        """Refresh an existing website document by staging a new version."""
        _ = owner_user_id
        doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
        if not doc or doc.is_deleted or doc.source_type != "website" or not doc.source_url:
            raise DocumentDomainException(
                code=DocumentErrorCode.SYS_001,
                message=f"Website knowledge document '{document_id}' not found in workspace.",
                detail={"document_id": str(document_id)},
            )

        existing_job = await self.job_repo.get_by_document_id(doc.id, session)
        if existing_job and existing_job.status in {
            "CLAIMED", "PROCESSING", "VALIDATING", "EXTRACTING", "OCR", "CHUNKING", "EMBEDDING", "VECTOR_SYNC", "FETCHING"
        }:
            active_version = await self.doc_repo.get_version_by_id(existing_job.version_id, session) if existing_job.version_id else doc.versions[0]
            return doc, active_version or doc.versions[0], existing_job

        max_v = max((v.version_number for v in doc.versions), default=1)
        next_version_number = max_v + 1

        storage_key = get_versioned_path(
            tenant_id=tenant_id,
            document_id=doc.id,
            version_number=next_version_number,
            category="original",
            filename="snapshot.html",
        )

        storage_obj = StorageObject(
            provider="local",
            bucket_or_container="raguard-storage",
            object_key=storage_key,
            file_size_bytes=0,
            mime_type="text/html",
            checksum_sha256="pending_fetch",
        )
        storage_obj = await self.storage_repo.create(storage_obj, session)

        staged_version = DocumentVersion(
            document_id=doc.id,
            version_number=next_version_number,
            storage_object_id=storage_obj.id,
            content_hash="pending_fetch",
            is_active_vector=False,
        )
        staged_version = await self.doc_repo.add_version(staged_version, session)

        job = ProcessingJob(
            document_id=doc.id,
            version_id=staged_version.id,
            status=DocumentStatus.PENDING,
            current_step="fetch",
            retry_count=0,
            max_retries=3,
        )
        job = await self.job_repo.create(job, session)
        await session.commit()

        await JobDispatcher.dispatch_job(job, session=session, queue="ingestion")
        await session.commit()

        return doc, staged_version, job

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
            "FETCHING": 15,
            "VALIDATING": 20,
            "EXTRACTING": 30,
            "OCR": 40,
            "MANIFEST_GENERATING": 45,
            "PROCESSED": 50,
            "CHUNKING": 65,
            "EMBEDDING": 80,
            "VECTOR_SYNC": 90,
            "READY": 100,
            "FAILED": 100,
        }

        progress = status_map.get(doc.status, 15)

        # If it's still UPLOADED, use job progress if available, but cap it so it never exceeds PROCESSED
        if doc.status == DocumentStatus.UPLOADED and job and job.current_step:
            job_step_progress = {
                "fetch": 15,
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
            current_step=job.current_step if (job and job.current_step) else doc.status.lower(),
            progress_percent=progress,
            retry_count=(job.retry_count or 0) if job else 0,
            error_code=job.error_code if job else None,
            error_message=job.error_message if job else None,
            updated_at=doc.updated_at or doc.created_at or datetime.now(UTC),
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
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> DocumentListResponse:
        """List documents within a tenant namespace with pagination, search, and sorting."""
        items, total = await self.doc_repo.list_documents(
            tenant_id=tenant_id,
            session=session,
            page=page,
            page_size=page_size,
            status=status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
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
        """Soft-delete a document, remove physical artifacts from storage, and clean up Qdrant vectors."""
        doc = await self.doc_repo.get_by_id_with_versions(
            document_id, tenant_id, session
        )
        if not doc:
            return False

        # Soft delete in database
        success = await self.doc_repo.delete(document_id, tenant_id, session)
        if not success:
            return False

        # Delete physical artifacts from storage prefix (`documents/{tenant_id}/{document_id}`)
        prefix = f"documents/{tenant_id}/{document_id}"
        await self.storage.delete_prefix(prefix)

        # Clean up vector points from Qdrant via VectorStorageService
        from backend.modules.vector.services.vector_service import VectorStorageService

        vector_service = VectorStorageService(session=session)
        await vector_service.delete_document_points(
            document_id=document_id, tenant_id=tenant_id
        )

        # Log deletion audit event
        payload = create_domain_event(
            event_type=EVENT_DOCUMENT_DELETED,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        event_log = DocumentEventLog(
            document_id=document_id,
            event_type=EVENT_DOCUMENT_DELETED,
            payload=payload.model_dump(mode="json"),
            triggered_by="delete_api",
        )
        await self.event_repo.append_event(event_log, session)
        await session.commit()

        # Invalidate BM25 sparse index via domain event
        try:
            from dataclasses import dataclass
            from backend.core.events.base import BaseEvent
            from backend.core.events.dispatcher import get_dispatcher
            from backend.core.events.types import EventType

            @dataclass(frozen=True)
            class DocumentDeletedDomainEvent(BaseEvent):
                event_type: EventType = EventType.DOCUMENT_DELETED
                tenant_id: str = ""
                document_id: str = ""

            del_event = DocumentDeletedDomainEvent(
                tenant_id=tenant_id, document_id=str(document_id)
            )
            dispatcher = get_dispatcher()
            await dispatcher.publish(del_event)
        except Exception as exc:
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "Failed to publish DOCUMENT_DELETED event", error=str(exc)
            )

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

            # Resilient dispatch of Celery ingestion task
            from backend.document.services.job_dispatcher import JobDispatcher
            await JobDispatcher.dispatch_job(job, session=session, queue="ingestion")
            await session.commit()

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

            # Resilient dispatch of Celery ingestion task
            from backend.document.services.job_dispatcher import JobDispatcher
            await JobDispatcher.dispatch_job(job, session=session, queue="ingestion")
            await session.commit()

            return doc, version, job

    async def get_original_file_stream(
        self,
        document_id: uuid.UUID,
        tenant_id: str,
        session: AsyncSession,
        version_id: uuid.UUID | None = None,
    ) -> tuple[BinaryIO, str, str, int]:
        """Retrieve original binary file stream securely without path exposure.

        Returns:
            tuple of (stream, original_filename, mime_type, file_size_bytes)
        """
        doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
        if not doc:
            raise DocumentDomainException("STORE_002", "Document not found")

        target_version: DocumentVersion | None = None
        if version_id:
            target_version = next((v for v in doc.versions if v.id == version_id), None)
            if not target_version:
                raise DocumentDomainException("STORE_002", "Target document version not found")
        else:
            if doc.latest_version_id:
                target_version = next((v for v in doc.versions if v.id == doc.latest_version_id), None)
            if not target_version and doc.versions:
                target_version = max(doc.versions, key=lambda v: v.version_number)

        if not target_version or not target_version.storage_object:
            raise DocumentDomainException("STORE_002", "Document version storage object not found")

        storage_obj = target_version.storage_object
        if not await self.storage.object_exists(storage_obj.object_key):
            raise DocumentDomainException(
                "STORE_002", "Physical storage file is missing on storage volume"
            )

        stream = await self.storage.get_stream(storage_obj.object_key)
        filename = doc.original_filename or doc.filename
        mime_type = storage_obj.mime_type or "application/octet-stream"
        file_size = storage_obj.file_size_bytes or 0

        return stream, filename, mime_type, file_size

    async def get_extracted_text_stream(
        self,
        document_id: uuid.UUID,
        tenant_id: str,
        session: AsyncSession,
        version_id: uuid.UUID | None = None,
    ) -> tuple[BinaryIO, str, int]:
        """Retrieve normalized extracted text artifact stream securely.

        Returns:
            tuple of (stream, download_filename, file_size_bytes)
        """
        doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
        if not doc:
            raise DocumentDomainException("STORE_002", "Document not found")

        target_version: DocumentVersion | None = None
        if version_id:
            target_version = next((v for v in doc.versions if v.id == version_id), None)
            if not target_version:
                raise DocumentDomainException("STORE_002", "Target document version not found")
        else:
            if doc.latest_version_id:
                target_version = next((v for v in doc.versions if v.id == doc.latest_version_id), None)
            if not target_version and doc.versions:
                target_version = max(doc.versions, key=lambda v: v.version_number)

        if not target_version or not target_version.extracted_text_path:
            raise DocumentDomainException(
                "VAL_001", "Extracted content is not yet available for this document"
            )

        if not await self.storage.object_exists(target_version.extracted_text_path):
            raise DocumentDomainException(
                "STORE_002", "Extracted text artifact is missing on storage volume"
            )

        stream = await self.storage.get_stream(target_version.extracted_text_path)
        content_bytes = stream.read()
        stream.seek(0)
        file_size = len(content_bytes)
        download_filename = f"{doc.filename}.extracted.txt"

        return stream, download_filename, file_size

    async def retry_document(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> tuple[Document, ProcessingJob]:
        """Retry processing for a FAILED document using existing uploaded storage artifact."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found")
            if doc.status in (DocumentStatus.ARCHIVED, DocumentStatus.DELETED):
                raise DocumentDomainException("VAL_001", f"Cannot retry a {doc.status.lower()} document")
            if doc.status != DocumentStatus.FAILED:
                raise DocumentDomainException(
                    "VAL_001",
                    f"Only documents in FAILED status can be retried (current status: {doc.status}). Use re-ingest for completed documents."
                )

            # Resolve target version (active or latest)
            target_version: DocumentVersion | None = None
            if doc.latest_version_id:
                target_version = next((v for v in doc.versions if v.id == doc.latest_version_id), None)
            if not target_version and doc.versions:
                target_version = max(doc.versions, key=lambda v: v.version_number)

            if not target_version or not target_version.storage_object:
                raise DocumentDomainException("STORE_002", "Storage object metadata missing for document")

            # Execute StoragePreflightValidator
            from backend.document.storage.preflight import StoragePreflightValidator
            preflight = StoragePreflightValidator.validate(
                target_version.storage_object, expected_tenant_id=tenant_id
            )
            if not preflight.is_valid:
                raise DocumentDomainException(
                    "STORE_002",
                    f"Storage pre-flight check failed: {preflight.error_message or 'Physical storage object missing'}"
                )

            # Find existing processing job or create a new one
            job = await self.job_repo.get_by_document_id(doc.id, session)
            if not job:
                job = ProcessingJob(
                    document_id=doc.id,
                    version_id=target_version.id,
                    status=DocumentStatus.PENDING,
                    current_step="upload",
                    retry_count=0,
                    max_retries=3,
                )
                job = await self.job_repo.create(job, session)
            else:
                job.version_id = target_version.id
                job.status = DocumentStatus.PENDING
                job.current_step = "upload"
                job.error_code = None
                job.error_message = None
                job.retry_count = 0
                job.dispatch_state = DispatchState.PENDING_DISPATCH.value
                job.dispatch_error = None
                job.completed_at = None

            doc.status = DocumentStatus.UPLOADED
            await session.flush()

            # Record domain event
            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_RETRIED,
                tenant_id=tenant_id,
                document_id=doc.id,
                job_id=job.id,
                data={
                    "version_id": str(target_version.id),
                    "version_number": target_version.version_number,
                },
            )
            event_log = DocumentEventLog(
                document_id=doc.id,
                job_id=job.id,
                event_type=EVENT_DOCUMENT_RETRIED,
                payload=payload.model_dump(mode="json"),
                triggered_by="retry_api",
            )
            await self.event_repo.append_event(event_log, session)
            await session.commit()

            # Dispatch Celery ingestion task
            from backend.document.services.job_dispatcher import JobDispatcher
            await JobDispatcher.dispatch_job(job, session=session, queue="ingestion", force=True)
            await session.commit()

            return doc, job

    async def reingest_document(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> tuple[Document, ProcessingJob]:
        """Re-ingest an existing document from scratch (wipes chunks/vectors, re-runs complete pipeline)."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found")
            if doc.status in (DocumentStatus.ARCHIVED, DocumentStatus.DELETED):
                raise DocumentDomainException("VAL_001", f"Cannot re-ingest a {doc.status.lower()} document")

            # Resolve target version
            target_version: DocumentVersion | None = None
            if doc.latest_version_id:
                target_version = next((v for v in doc.versions if v.id == doc.latest_version_id), None)
            if not target_version and doc.versions:
                target_version = max(doc.versions, key=lambda v: v.version_number)

            if not target_version or not target_version.storage_object:
                raise DocumentDomainException("STORE_002", "Storage object metadata missing for document")

            # Execute StoragePreflightValidator
            from backend.document.storage.preflight import StoragePreflightValidator
            preflight = StoragePreflightValidator.validate(
                target_version.storage_object, expected_tenant_id=tenant_id
            )
            if not preflight.is_valid:
                raise DocumentDomainException(
                    "STORE_002",
                    f"Storage pre-flight check failed: {preflight.error_message or 'Physical storage object missing'}"
                )

            # Purge existing Qdrant vectors and DB chunks
            try:
                from backend.modules.vector.services.vector_service import VectorStorageService
                vector_service = VectorStorageService(session=session)
                await vector_service.delete_document_points(doc.id, tenant_id)
            except Exception as v_err:
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning("Failed to purge vectors during re-ingest", error=str(v_err), doc_id=str(doc.id))

            from sqlalchemy import delete
            from backend.modules.chunking.models.chunk import DocumentChunk
            await session.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.tenant_id == tenant_id,
                    DocumentChunk.document_id == doc.id,
                )
            )

            # Reset / Create ProcessingJob
            job = await self.job_repo.get_by_document_id(doc.id, session)
            if not job:
                job = ProcessingJob(
                    document_id=doc.id,
                    version_id=target_version.id,
                    status=DocumentStatus.PENDING,
                    current_step="upload",
                    retry_count=0,
                    max_retries=3,
                )
                job = await self.job_repo.create(job, session)
            else:
                job.version_id = target_version.id
                job.status = DocumentStatus.PENDING
                job.current_step = "upload"
                job.error_code = None
                job.error_message = None
                job.retry_count = 0
                job.dispatch_state = DispatchState.PENDING_DISPATCH.value
                job.dispatch_error = None
                job.completed_at = None

            doc.status = DocumentStatus.UPLOADED
            await session.flush()

            # Record domain event
            payload = create_domain_event(
                event_type=EVENT_DOCUMENT_REINGESTED,
                tenant_id=tenant_id,
                document_id=doc.id,
                job_id=job.id,
                data={
                    "version_id": str(target_version.id),
                    "version_number": target_version.version_number,
                },
            )
            event_log = DocumentEventLog(
                document_id=doc.id,
                job_id=job.id,
                event_type=EVENT_DOCUMENT_REINGESTED,
                payload=payload.model_dump(mode="json"),
                triggered_by="reingest_api",
            )
            await self.event_repo.append_event(event_log, session)
            await session.commit()

            # Dispatch Celery ingestion task
            from backend.document.services.job_dispatcher import JobDispatcher
            await JobDispatcher.dispatch_job(job, session=session, queue="ingestion", force=True)
            await session.commit()

            return doc, job

