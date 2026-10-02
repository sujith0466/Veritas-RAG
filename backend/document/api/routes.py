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
from fastapi.responses import StreamingResponse
import urllib.parse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import require_role
from backend.core.dependencies.database import get_db
from backend.core.permissions.rbac import Role
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
    user: UserContext | Any | None,
) -> tuple[str, uuid.UUID | None]:
    tenant_id = getattr(user, "tenant_id", None)
    if not user or not tenant_id or str(tenant_id) == "None":
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Missing workspace context")
    return str(tenant_id), getattr(user, "id", None)


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
    user: UserContext = Depends(require_role(Role.MEMBER)),
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
    user: UserContext = Depends(require_role(Role.VIEWER)),
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
    user: UserContext = Depends(require_role(Role.VIEWER)),
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


def _format_content_disposition(filename: str) -> str:
    """Format RFC 5987 / 6266 Content-Disposition header with UTF-8 support."""
    ascii_name = filename.encode("ascii", "ignore").decode("ascii").replace('"', '\\"') or "download.bin"
    encoded_name = urllib.parse.quote(filename)
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'


@router.get(
    "/{document_id}/download",
    summary="Download original document binary",
    description="Stream the original uploaded binary file securely. Requires VIEWER role within the tenant.",
)
async def download_original_document(
    document_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(None, description="Optional specific version ID to download"),
    user: UserContext = Depends(require_role(Role.VIEWER)),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download original document file stream."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        stream, filename, mime_type, file_size = await service.get_original_file_stream(
            document_id=document_id,
            tenant_id=tenant_id,
            session=session,
            version_id=version_id,
        )
    except Exception as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    headers = {
        "Content-Disposition": _format_content_disposition(filename),
    }
    if file_size > 0:
        headers["Content-Length"] = str(file_size)

    return StreamingResponse(stream, media_type=mime_type, headers=headers)


@router.get(
    "/{document_id}/extracted-text",
    summary="Download normalized extracted text content",
    description="Stream the clean, extracted and normalized UTF-8 text content. Requires VIEWER role.",
)
async def download_extracted_text(
    document_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(None, description="Optional specific version ID"),
    user: UserContext = Depends(require_role(Role.VIEWER)),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download extracted text artifact stream."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        stream, filename, file_size = await service.get_extracted_text_stream(
            document_id=document_id,
            tenant_id=tenant_id,
            session=session,
            version_id=version_id,
        )
    except Exception as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        if "not yet available" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    headers = {
        "Content-Disposition": _format_content_disposition(filename),
    }
    if file_size > 0:
        headers["Content-Length"] = str(file_size)

    return StreamingResponse(stream, media_type="text/plain; charset=utf-8", headers=headers)



@router.get(
    "",
    response_model=SuccessResponse[DocumentListResponse],
    summary="List tenant documents",
    description="List all documents within the caller's tenant namespace with pagination, search, sorting, and optional status filter.",
)
async def list_documents(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status (PENDING, VALIDATING, EXTRACTING, PROCESSED, CHUNKING, EMBEDDING, VECTOR_SYNC, READY, FAILED)",
    ),
    q: str | None = Query(None, description="Search term across filename and original filename"),
    sort_by: str = Query("created_at", description="Sort field: created_at, filename, word_count, status, updated_at"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    user: UserContext = Depends(require_role(Role.VIEWER)),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[DocumentListResponse]:
    """List documents with pagination, search, and sorting."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    list_resp = await service.list_documents(
        tenant_id=tenant_id,
        session=session,
        page=page,
        page_size=page_size,
        status=status_filter,
        search=q,
        sort_by=sort_by,
        sort_order=sort_order,
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
    description="Soft-delete document database record, purge physical artifacts from storage, and delete Qdrant vectors.",
)
async def delete_document(
    request: Request,
    document_id: uuid.UUID,
    user: UserContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Delete document entity, clean up physical files, and remove vectors."""
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
    user: UserContext = Depends(require_role(Role.ADMIN)),
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
    user: UserContext = Depends(require_role(Role.ADMIN)),
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
    "/{document_id}/retry",
    response_model=SuccessResponse[dict[str, Any]],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry ingestion for a failed document",
    description="Retry the ingestion pipeline for a document currently in FAILED status, verifying storage artifact preflight.",
)
async def retry_document(
    request: Request,
    document_id: uuid.UUID,
    user: UserContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Retry failed document ingestion."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        doc, job = await service.retry_document(document_id, tenant_id, session)
    except Exception as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    return SuccessResponse(
        success=True,
        data={
            "document_id": str(doc.id),
            "job_id": str(job.id),
            "status": doc.status,
            "retried": True,
        },
        metadata=_build_metadata(request),
    )


@router.post(
    "/{document_id}/reingest",
    response_model=SuccessResponse[dict[str, Any]],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-ingest document from scratch",
    description="Re-extract, re-chunk, re-embed, and re-index an existing document from its original storage object, purging stale vectors.",
)
async def reingest_document(
    request: Request,
    document_id: uuid.UUID,
    user: UserContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Re-ingest an existing document."""
    tenant_id, _ = _resolve_tenant_and_owner(user)
    service = DocumentService()

    try:
        doc, job = await service.reingest_document(document_id, tenant_id, session)
    except Exception as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    return SuccessResponse(
        success=True,
        data={
            "document_id": str(doc.id),
            "job_id": str(job.id),
            "status": doc.status,
            "reingested": True,
        },
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
    user: UserContext = Depends(require_role(Role.MEMBER)),
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
    user: UserContext = Depends(require_role(Role.ADMIN)),
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
    user: UserContext = Depends(require_role(Role.MEMBER)),
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
    user: UserContext = Depends(require_role(Role.MEMBER)),
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
    user: UserContext = Depends(require_role(Role.MEMBER)),
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
