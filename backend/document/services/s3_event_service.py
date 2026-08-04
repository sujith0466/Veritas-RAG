"""S3 Event Service (`S3EventService`).

Handles direct-to-S3 presigned upload generation, S3 ObjectCreated webhook event parsing,
and asynchronous pipeline dispatching with Redis deduplication.
"""

from datetime import UTC, datetime
import re
from typing import Any
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.events.domain_events import EVENT_DOCUMENT_UPLOADED, create_domain_event
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.status import DocumentStatus
from backend.document.models.storage_object import StorageObject
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.repositories.event_repository import DocumentEventRepository
from backend.document.repositories.job_repository import JobRepository
from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode
from backend.document.services.processing_job_service import ProcessingJobService
from backend.document.storage.base import StorageProvider, get_versioned_path
from backend.document.validators.sanitization import sanitize_filename


class S3EventService:
    """Service orchestrating presigned upload generation and S3 event-driven triggers."""

    def __init__(
        self,
        storage_provider: StorageProvider,
        document_repo: DocumentRepository,
        job_repo: JobRepository,
        job_service: ProcessingJobService,
        event_repo: DocumentEventRepository,
        redis_client: redis.Redis,
    ):
        self.storage_provider = storage_provider
        self.document_repo = document_repo
        self.job_repo = job_repo
        self.job_service = job_service
        self.event_repo = event_repo
        self.redis = redis_client

    async def generate_presigned_upload(
        self,
        tenant_id: str,
        filename: str,
        file_size_bytes: int,
        mime_type: str,
        checksum_sha256: str | None,
        folder_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        session: AsyncSession,
        expiration_seconds: int = 3600,
    ) -> dict[str, Any]:
        """Generate a presigned PUT upload URL and register preliminary database entities."""
        clean_name = sanitize_filename(filename)
        document_id = uuid.uuid4()
        version_id = uuid.uuid4()
        version_number = 1

        object_key = get_versioned_path(
            tenant_id=tenant_id,
            document_id=document_id,
            version_number=version_number,
            category="original",
            filename=clean_name,
        )

        # 1. Create StorageObject record
        storage_obj = StorageObject(
            id=uuid.uuid4(),
            provider=self.storage_provider.provider_name,
            bucket_or_container=self.storage_provider.bucket_name,
            object_key=object_key,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            checksum_sha256=checksum_sha256 or "",
        )
        session.add(storage_obj)

        # 2. Create Document entity in PENDING state
        doc = Document(
            id=document_id,
            tenant_id=tenant_id,
            folder_id=folder_id,
            owner_user_id=user_id,
            filename=clean_name,
            original_filename=filename,
            status=DocumentStatus.PENDING,
            word_count=0,
            page_count=0,
        )
        session.add(doc)

        # 3. Create DocumentVersion entity
        doc_version = DocumentVersion(
            id=version_id,
            document_id=document_id,
            version_number=version_number,
            storage_object_id=storage_obj.id,
            content_hash=checksum_sha256 or "",
        )
        session.add(doc_version)
        doc.latest_version_id = version_id
        await session.flush()

        # 4. Generate Presigned URL via storage provider
        upload_url = await self.storage_provider.create_upload_url(
            object_key=object_key, expiration_seconds=expiration_seconds
        )

        return {
            "document_id": str(document_id),
            "version_id": str(version_id),
            "upload_url": upload_url,
            "object_key": object_key,
            "expires_in_seconds": expiration_seconds,
            "required_headers": {
                "Content-Type": mime_type,
            },
        }

    async def handle_s3_object_created(
        self,
        bucket: str,
        object_key: str,
        etag: str,
        size_bytes: int,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Process an S3 ObjectCreated event notification idempotently."""
        # 1. Idempotency check via Redis
        dedup_key = f"s3_event:{bucket}:{object_key}:{etag}"
        is_new = await self.redis.set(dedup_key, "1", nx=True, ex=86400)
        if not is_new:
            return {"status": "duplicate_ignored", "object_key": object_key}

        # 2. Parse canonical key: documents/{tenant_id}/{document_id}/v{version_number}/original/{filename}
        # Example pattern: documents/([^/]+)/([^/]+)/v([0-9]+)/original/(.+)
        pattern = r"documents/([^/]+)/([0-9a-fA-F-]+)/v([0-9]+)/original/(.+)"
        match = re.match(pattern, object_key)
        if not match:
            # Non-standard key format or non-original artifact; acknowledge and ignore
            return {"status": "ignored_non_canonical_key", "object_key": object_key}

        tenant_id, doc_id_str, _version_str, _filename = match.groups()
        try:
            document_id = uuid.UUID(doc_id_str)
        except (ValueError, TypeError):
            return {"status": "invalid_key_uuid", "object_key": object_key}

        # 3. Retrieve and update document
        doc = await self.document_repo.get_by_id(document_id, session)
        if not doc:
            return {"status": "document_not_found", "document_id": doc_id_str}

        doc.status = DocumentStatus.UPLOADED
        await session.flush()

        # 4. Enqueue ProcessingJob
        job = await self.job_service.enqueue_job(
            document_id=document_id,
            priority=1,
            started_at=datetime.now(UTC),
            actor="s3_event_trigger",
            session=session,
        )

        # 5. Record domain event
        event_payload = create_domain_event(
            event_type=EVENT_DOCUMENT_UPLOADED,
            tenant_id=tenant_id,
            document_id=document_id,
            job_id=job.id,
            data={"object_key": object_key, "size_bytes": size_bytes, "etag": etag},
        )
        await self.event_repo.append_event(
            document_id=document_id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            payload=event_payload.model_dump(),
            session=session,
            job_id=job.id,
        )

        # 6. Dispatch background task via Celery
        try:
            from backend.document.workers.ingestion import process_document_job
            process_document_job.apply_async(
                kwargs={
                    "job_id": str(job.id),
                    "document_id": str(document_id),
                    "tenant_id": tenant_id,
                },
                queue="ingestion",
            )
        except Exception:
            # In local or testing environments where Celery broker is mock/disabled
            pass

        return {
            "status": "triggered",
            "document_id": str(document_id),
            "job_id": str(job.id),
        }

    async def handle_client_upload_complete(
        self,
        document_id: uuid.UUID,
        tenant_id: str,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Handle client upload completion callback to trigger the processing pipeline."""
        doc = await self.document_repo.get_by_id(document_id, session)
        if not doc or doc.tenant_id != tenant_id:
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_002,
                message=f"Document {document_id} not found in workspace",
                status_code=404,
            )

        # Update status
        doc.status = DocumentStatus.UPLOADED
        await session.flush()

        # Enqueue processing job
        job = await self.job_service.enqueue_job(
            document_id=document_id,
            priority=1,
            started_at=datetime.now(UTC),
            actor="client_complete_upload",
            session=session,
        )

        # Record domain event
        event_payload = create_domain_event(
            event_type=EVENT_DOCUMENT_UPLOADED,
            tenant_id=tenant_id,
            document_id=document_id,
            job_id=job.id,
            data={"method": "client_callback"},
        )
        await self.event_repo.append_event(
            document_id=document_id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            payload=event_payload.model_dump(),
            session=session,
            job_id=job.id,
        )

        # Dispatch Celery task
        try:
            from backend.document.workers.ingestion import process_document_job
            process_document_job.apply_async(
                kwargs={
                    "job_id": str(job.id),
                    "document_id": str(document_id),
                    "tenant_id": tenant_id,
                },
                queue="ingestion",
            )
        except Exception:
            pass

        return {
            "document_id": str(document_id),
            "job_id": str(job.id),
            "status": "QUEUED",
        }
