"""Document Intelligence REST API endpoints (`ADR-005`).

Provides endpoints for file upload (`POST /upload`), status inspection (`GET /{id}/status`),
document details and manifest (`GET /{id}`), listing (`GET /`), and deletion (`DELETE /{id}`).
"""

from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.document.schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    ProcessingStatusResponse,
    UploadResponse,
)
from backend.document.services import DocumentService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Document Intelligence"])


def _build_metadata(request: Request) -> ResponseMetadata:
    """Helper to construct standard ResponseMetadata for envelopes."""
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


def _resolve_tenant_and_owner(
    user: Any | None,
    header_tenant: str | None,
) -> tuple[str, uuid.UUID | None]:
    """Resolve effective tenant namespace and owner user ID from auth context or headers."""
    if user:
        tenant_id = user.tenant_id or header_tenant or "default_tenant"
        owner_id = getattr(user, "id", None)
        return tenant_id, owner_id
    tenant_id = header_tenant or "default_tenant"
    return tenant_id, None


@router.post(
    "/upload",
    response_model=SuccessResponse[UploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest and process a document",
    description="Upload a document (`multipart/form-data`) for validation, extraction, OCR fallback, and manifest generation.",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[UploadResponse]:
    """Handle synchronous upload screening, storage persistence, and Celery job dispatch."""
    tenant_id, owner_id = _resolve_tenant_and_owner(user, x_tenant_id)
    service = DocumentService()

    doc, version, job = await service.upload_document(
        stream=file.file,
        filename=file.filename or "unknown.txt",
        declared_mime=file.content_type or "application/octet-stream",
        tenant_id=tenant_id,
        owner_user_id=owner_id,
        session=session,
    )

    file_size = version.storage_object.file_size_bytes if version.storage_object else 0

    return SuccessResponse(
        success=True,
        data=UploadResponse(
            document_id=doc.id,
            version_id=version.id,
            job_id=job.id,
            status=doc.status,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_size_bytes=file_size,
            created_at=doc.created_at,
        ),
        metadata=_build_metadata(request),
    )


@router.get(
    "/{document_id}/status",
    response_model=SuccessResponse[ProcessingStatusResponse],
    summary="Check document processing status",
    description="Inspect real-time ingestion status, active step, progress percentage, and retry/error state.",
)
async def get_document_status(
    request: Request,
    document_id: uuid.UUID,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[ProcessingStatusResponse]:
    """Retrieve processing status for a specific document."""
    tenant_id, _ = _resolve_tenant_and_owner(user, x_tenant_id)
    service = DocumentService()

    status_resp = await service.get_status(document_id, tenant_id, session)
    if not status_resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return SuccessResponse(
        success=True,
        data=status_resp,
        metadata=_build_metadata(request),
    )


@router.get(
    "/{document_id}",
    response_model=SuccessResponse[DocumentDetailResponse],
    summary="Get document details and canonical manifest",
    description="Fetch complete document metadata, version history, and canonical manifest if processing is finished.",
)
async def get_document_detail(
    request: Request,
    document_id: uuid.UUID,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[DocumentDetailResponse]:
    """Retrieve detailed document metadata and manifest."""
    tenant_id, _ = _resolve_tenant_and_owner(user, x_tenant_id)
    service = DocumentService()

    detail_resp = await service.get_document_detail(document_id, tenant_id, session)
    if not detail_resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return SuccessResponse(
        success=True,
        data=detail_resp,
        metadata=_build_metadata(request),
    )


@router.get(
    "",
    response_model=SuccessResponse[DocumentListResponse],
    summary="List tenant documents",
    description="List all documents within the caller's tenant namespace with pagination and optional status filter.",
)
async def list_documents(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status (PENDING, VALIDATING, EXTRACTING, PROCESSED, FAILED)"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[DocumentListResponse]:
    """List documents with pagination."""
    tenant_id, _ = _resolve_tenant_and_owner(user, x_tenant_id)
    service = DocumentService()

    list_resp = await service.list_documents(
        tenant_id=tenant_id,
        session=session,
        page=page,
        page_size=page_size,
        status=status_filter,
    )

    return SuccessResponse(
        success=True,
        data=list_resp,
        metadata=_build_metadata(request),
    )


@router.delete(
    "/{document_id}",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Soft-delete document and purge artifacts",
    description="Soft-delete document database record and remove all physical artifacts from storage.",
)
async def delete_document(
    request: Request,
    document_id: uuid.UUID,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Delete document entity and clean up physical files."""
    tenant_id, _ = _resolve_tenant_and_owner(user, x_tenant_id)
    service = DocumentService()

    success = await service.delete_document(document_id, tenant_id, session)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or delete failed")

    return SuccessResponse(
        success=True,
        data={"deleted": True, "document_id": str(document_id)},
        metadata=_build_metadata(request),
    )
