"""Document Intelligence REST API endpoints (`ADR-005`).

Provides endpoints for file upload (`POST /upload`), status inspection (`GET /{id}/status`),
document details and manifest (`GET /{id}`), listing (`GET /`), and deletion (`DELETE /{id}`).
"""

from typing import Any
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
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
) -> tuple[str, uuid.UUID | None]:
    if not user or not getattr(user, "workspace_name", None) or user.workspace_name == "None":
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing workspace context")
    return str(user.workspace_name), getattr(user, "id", None)


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
    relative_path: str | None = Form(default=None),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[UploadResponse]:
    """Handle synchronous upload screening, storage persistence, and Celery job dispatch."""
    tenant_id, owner_id = _resolve_tenant_and_owner(user)

    ws_uuid = None
    try:
        ws_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        pass

    from backend.modules.analytics.services.quota import QuotaGovernor
    governor = QuotaGovernor()
    is_exceeded, _, _, _ = await governor.check_quota(workspace_id=ws_uuid, tenant_id=tenant_id, session=session)
    if is_exceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Workspace token quota exceeded",
            headers={"Retry-After": "3600"},
        )

    service = DocumentService()

    doc, version, job = await service.upload_document(
        stream=file.file,
        filename=file.filename or "unknown.txt",
        declared_mime=file.content_type or "application/octet-stream",
        tenant_id=tenant_id,
        owner_user_id=owner_id,
        session=session,
        relative_path=relative_path,
    )

    file_size = getattr(file, "size", 0) or 0

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
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[ProcessingStatusResponse]:
    """Retrieve processing status for a specific document."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    status_resp = await service.get_status(document_id, tenant_id, session)
    if not status_resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

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
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[DocumentDetailResponse]:
    """Retrieve detailed document metadata and manifest."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    detail_resp = await service.get_document_detail(document_id, tenant_id, session)
    if not detail_resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

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
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status (PENDING, VALIDATING, EXTRACTING, PROCESSED, FAILED)",
    ),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[DocumentListResponse]:
    """List documents with pagination."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
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
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Delete document entity and clean up physical files."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    success = await service.delete_document(document_id, tenant_id, session)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or delete failed",
        )

    return SuccessResponse(
        success=True,
        data={"deleted": True, "document_id": str(document_id)},
        metadata=_build_metadata(request),
    )


@router.post(
    "/{document_id}/archive",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Archive a document",
    description="Archive a document and asynchronously remove its vectors from Qdrant.",
)
async def archive_document(
    request: Request,
    document_id: uuid.UUID,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Archive a document."""
    tenant_id, owner_id = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        await service.archive_document(document_id, tenant_id, owner_id, session)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SuccessResponse(
        success=True,
        data={"archived": True, "document_id": str(document_id)},
        metadata=_build_metadata(request),
    )


@router.post(
    "/{document_id}/restore",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Restore an archived document",
    description="Restore an archived document and re-sync its vectors to Qdrant.",
)
async def restore_document(
    request: Request,
    document_id: uuid.UUID,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Restore a document."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        await service.restore_document(document_id, tenant_id, session)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SuccessResponse(
        success=True,
        data={"restored": True, "document_id": str(document_id)},
        metadata=_build_metadata(request),
    )


@router.post(
    "/{document_id}/versions",
    response_model=SuccessResponse[UploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a new document version",
    description="Upload a new file version for an existing document. Older versions will have their vectors removed once processed.",
)
async def upload_document_version(
    request: Request,
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[UploadResponse]:
    """Upload a new version of a document."""
    tenant_id, owner_id = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        doc, version, job = await service.upload_new_version(
            document_id=document_id,
            stream=file.file,
            filename=file.filename or "unknown.txt",
            declared_mime=file.content_type or "application/octet-stream",
            tenant_id=tenant_id,
            owner_user_id=owner_id,
            session=session,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    file_size = getattr(file, "size", 0) or 0

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


@router.post(
    "/{document_id}/versions/{version_id}/rollback",
    response_model=SuccessResponse[UploadResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rollback to a previous document version",
    description="Rollback to an older version. Clones the older version as the new active version and processes it.",
)
async def rollback_document_version(
    request: Request,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[UploadResponse]:
    """Rollback to a previous version."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        doc, version, job = await service.rollback_to_version(
            document_id=document_id,
            target_version_id=version_id,
            tenant_id=tenant_id,
            session=session,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SuccessResponse(
        success=True,
        data=UploadResponse(
            document_id=doc.id,
            version_id=version.id,
            job_id=job.id,
            status=doc.status,
            filename=doc.filename,
            original_filename=doc.original_filename,
            file_size_bytes=0,
            created_at=doc.created_at,
        ),
        metadata=_build_metadata(request),
    )


from backend.document.schemas.metadata import MetadataUpdatePayload


@router.put(
    "/{document_id}/metadata",
    response_model=SuccessResponse[dict],
    summary="Overwrite document user metadata",
)
async def update_document_metadata(
    document_id: uuid.UUID,
    payload: MetadataUpdatePayload,
    request: Request,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Overwrite all user_metadata keys for a document."""
    tenant_id, _ = _resolve_tenant_and_owner(user)

    from backend.document.services.metadata_service import MetadataService
    from backend.document.workers.metadata_sync import sync_document_metadata_to_vectors_job

    service = MetadataService(session)
    updated_meta = await service.update_metadata(document_id, tenant_id, payload.metadata)

    sync_document_metadata_to_vectors_job.apply_async(
        kwargs={"document_id": str(document_id), "tenant_id": tenant_id}
    )

    return SuccessResponse(success=True, data=updated_meta, metadata=_build_metadata(request))


@router.patch(
    "/{document_id}/metadata",
    response_model=SuccessResponse[dict],
    summary="Patch document user metadata",
)
async def patch_document_metadata(
    document_id: uuid.UUID,
    payload: MetadataUpdatePayload,
    request: Request,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Merge new keys into the document's user_metadata."""
    tenant_id, _ = _resolve_tenant_and_owner(user)

    from backend.document.services.metadata_service import MetadataService
    from backend.document.workers.metadata_sync import sync_document_metadata_to_vectors_job

    service = MetadataService(session)
    updated_meta = await service.patch_metadata(document_id, tenant_id, payload.metadata)

    sync_document_metadata_to_vectors_job.apply_async(
        kwargs={"document_id": str(document_id), "tenant_id": tenant_id}
    )

    return SuccessResponse(success=True, data=updated_meta, metadata=_build_metadata(request))


@router.delete(
    "/{document_id}/metadata/{key}",
    response_model=SuccessResponse[dict],
    summary="Remove a specific metadata key",
)
async def remove_document_metadata_key(
    document_id: uuid.UUID,
    key: str,
    request: Request,
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    """Remove a specific key from the document's user_metadata."""
    tenant_id, _ = _resolve_tenant_and_owner(user)

    from backend.document.services.metadata_service import MetadataService
    from backend.document.workers.metadata_sync import sync_document_metadata_to_vectors_job

    service = MetadataService(session)
    updated_meta = await service.remove_metadata_key(document_id, tenant_id, key)

    sync_document_metadata_to_vectors_job.apply_async(
        kwargs={"document_id": str(document_id), "tenant_id": tenant_id}
    )

    return SuccessResponse(success=True, data=updated_meta, metadata=_build_metadata(request))
