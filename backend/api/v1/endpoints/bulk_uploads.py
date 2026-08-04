"""Bulk Upload REST API endpoints."""

from typing import Any
import uuid

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.document.schemas.bulk_upload import (
    BatchProgressResponse,
    BulkUploadRequest,
    BulkUploadResponse,
    PresignedUrlDTO,
)
from backend.document.services.bulk_upload_service import BulkUploadService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/bulk-uploads", tags=["Bulk Uploads"])


def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


def _resolve_tenant_and_owner(
    user: Any | None,
    header_tenant: str | None,
) -> tuple[str, uuid.UUID | None]:
    if user:
        tenant_id = user.tenant_id or header_tenant or "default_tenant"
        owner_id = getattr(user, "id", None)
        return tenant_id, owner_id
    tenant_id = header_tenant or "default_tenant"
    return tenant_id, None


@router.post(
    "",
    response_model=SuccessResponse[BulkUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a bulk upload batch",
)
async def initiate_bulk_upload(
    payload: BulkUploadRequest,
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[BulkUploadResponse]:
    """Initiate a bulk upload and return presigned POST URLs."""
    tenant_id, owner_id = _resolve_tenant_and_owner(user, x_tenant_id)

    # In a real implementation we would:
    # 1. Check workspace quotas.
    # 2. Check redis token bucket for rate limits.
    # 3. Create Document / DocumentVersion rows in DB.
    # 4. Generate S3 Presigned URLs for each document.

    service = BulkUploadService(session)
    batch = await service.create_batch(tenant_id, owner_id or uuid.uuid4(), len(payload.files))

    urls = []
    for file_intent in payload.files:
        doc_id = uuid.uuid4()
        urls.append(
            PresignedUrlDTO(
                filename=file_intent.filename,
                url=f"https://s3-mock.amazonaws.com/{tenant_id}/{doc_id}",
                fields={"AWSAccessKeyId": "MOCK", "signature": "MOCK"},
                document_id=doc_id,
            )
        )

    return SuccessResponse(
        success=True,
        data=BulkUploadResponse(
            batch_id=batch.id,
            presigned_urls=urls,
        ),
        metadata=_build_metadata(request)
    )


@router.get(
    "/{batch_id}",
    response_model=SuccessResponse[BatchProgressResponse],
    summary="Get bulk upload batch progress",
)
async def get_batch_progress(
    batch_id: uuid.UUID,
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[BatchProgressResponse]:
    """Get real-time progress for a bulk batch."""
    tenant_id, _ = _resolve_tenant_and_owner(user, x_tenant_id)
    service = BulkUploadService(session)

    progress = await service.get_progress(batch_id, tenant_id)
    if "error" in progress:
        return SuccessResponse(success=False, data=progress, metadata=_build_metadata(request))

    return SuccessResponse(
        success=True,
        data=BatchProgressResponse(**progress),
        metadata=_build_metadata(request)
    )


@router.post(
    "/{batch_id}/cancel",
    response_model=SuccessResponse[dict],
    summary="Cancel a bulk upload batch",
)
async def cancel_bulk_upload(
    batch_id: uuid.UUID,
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Cancel a pending/processing bulk upload batch."""
    tenant_id, _ = _resolve_tenant_and_owner(user, x_tenant_id)
    service = BulkUploadService(session)

    success = await service.cancel_batch(batch_id, tenant_id)

    return SuccessResponse(
        success=success,
        data={"cancelled": success},
        metadata=_build_metadata(request)
    )
