"""Storage Webhooks and Direct-to-S3 Upload API (`storage_webhooks.py`).

Provides endpoints for:
- Requesting presigned S3 upload URLs (`POST /workspaces/{workspace_id}/documents/presigned-upload`)
- Client upload completion notification (`POST /workspaces/{workspace_id}/documents/{document_id}/upload-complete`)
- S3 ObjectCreated EventBridge / SNS Webhook (`POST /webhooks/s3-events`)
"""

from typing import Any
import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.cache.client import get_redis_client
from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.rbac import require_role
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.repositories.event_repository import DocumentEventRepository
from backend.document.repositories.job_audit_repository import JobAuditRepository
from backend.document.repositories.job_repository import JobRepository
from backend.document.repositories.job_step_repository import JobStepRepository
from backend.document.services.processing_job_service import ProcessingJobService
from backend.document.services.s3_event_service import S3EventService
from backend.document.storage.cloud import S3StorageProvider
from backend.document.storage.local import LocalStorageProvider

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Storage & Ingestion"])


class PresignedUploadRequest(BaseModel):
    """Schema for requesting a presigned direct-to-S3 upload URL."""

    filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME content type")
    checksum_sha256: str | None = Field(default=None, description="Optional SHA256 checksum")
    folder_id: uuid.UUID | None = Field(default=None, description="Target folder ID")


class PresignedUploadResponse(BaseModel):
    """Schema for presigned upload URL details."""

    document_id: str
    version_id: str
    upload_url: str
    object_key: str
    expires_in_seconds: int
    required_headers: dict[str, str]


class ClientUploadCompleteRequest(BaseModel):
    """Schema for client signaling completed S3 PUT."""

    etag: str | None = Field(default=None, description="S3 ETag from PUT response")


def _get_storage_provider():
    import os
    provider_type = os.getenv("STORAGE_PROVIDER", "local").lower()
    if provider_type == "s3":
        bucket = os.getenv("S3_BUCKET_NAME", "raguard-docs")
        region = os.getenv("AWS_REGION", "us-east-1")
        endpoint = os.getenv("S3_ENDPOINT_URL", None)
        return S3StorageProvider(bucket=bucket, region=region, endpoint_url=endpoint)
    return LocalStorageProvider()


async def _get_s3_event_service(session: AsyncSession) -> S3EventService:
    redis_client = get_redis_client()
    storage = _get_storage_provider()
    doc_repo = DocumentRepository()
    job_repo = JobRepository()
    step_repo = JobStepRepository()
    audit_repo = JobAuditRepository()
    event_repo = DocumentEventRepository()
    job_service = ProcessingJobService(
        job_repo=job_repo,
        step_repo=step_repo,
        audit_repo=audit_repo,
        redis_client=redis_client,
    )
    return S3EventService(
        storage_provider=storage,
        document_repo=doc_repo,
        job_repo=job_repo,
        job_service=job_service,
        event_repo=event_repo,
        redis_client=redis_client,
    )


@router.post(
    "/workspaces/{workspace_id}/documents/presigned-upload",
    response_model=SuccessResponse[PresignedUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate presigned S3 upload URL",
)
async def generate_presigned_upload(
    workspace_id: uuid.UUID,
    payload: PresignedUploadRequest,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "owner", "member"])),
) -> SuccessResponse[PresignedUploadResponse]:
    """Generate a direct-to-S3 presigned upload URL for high-throughput ingress."""
    user_id = getattr(user, "id", None) if user else None
    service = await _get_s3_event_service(session)

    res = await service.generate_presigned_upload(
        tenant_id=str(workspace_id),
        filename=payload.filename,
        file_size_bytes=payload.file_size_bytes,
        mime_type=payload.mime_type,
        checksum_sha256=payload.checksum_sha256,
        folder_id=payload.folder_id,
        user_id=user_id,
        session=session,
    )
    await session.commit()

    return SuccessResponse(
        success=True,
        data=PresignedUploadResponse(**res),
        metadata=ResponseMetadata(request_id=str(uuid.uuid4())),
    )


@router.post(
    "/workspaces/{workspace_id}/documents/{document_id}/upload-complete",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Client upload complete notification",
)
async def client_upload_complete(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ClientUploadCompleteRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "owner", "member"])),
) -> SuccessResponse[dict[str, Any]]:
    """Acknowledge client-side S3 PUT completion and enqueue background processing."""
    service = await _get_s3_event_service(session)
    result = await service.handle_client_upload_complete(
        document_id=document_id,
        tenant_id=str(workspace_id),
        session=session,
    )
    await session.commit()
    return SuccessResponse(
        success=True,
        data=result,
        metadata=ResponseMetadata(request_id=str(uuid.uuid4())),
    )


@router.post(
    "/webhooks/s3-events",
    summary="S3 ObjectCreated webhook handler",
)
async def handle_s3_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Process incoming AWS S3 ObjectCreated / EventBridge notifications."""
    body = await request.json()
    service = await _get_s3_event_service(session)

    results = []
    # Standard AWS S3 notification JSON structure contains 'Records'
    records = body.get("Records", [])
    for rec in records:
        s3_data = rec.get("s3", {})
        bucket = s3_data.get("bucket", {}).get("name", "")
        obj_key = s3_data.get("object", {}).get("key", "")
        etag = s3_data.get("object", {}).get("eTag", "")
        size = s3_data.get("object", {}).get("size", 0)

        if bucket and obj_key:
            res = await service.handle_s3_object_created(
                bucket=bucket,
                object_key=obj_key,
                etag=etag,
                size_bytes=size,
                session=session,
            )
            results.append(res)

    await session.commit()
    return {"status": "processed", "results": results}
