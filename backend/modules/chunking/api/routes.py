"""Chunking & Document Processing REST API routes (`/api/v1/chunks`).

Provides endpoints for strategy listing, explicit chunking triggers (`POST /process/{id}`),
paginated chunk exploration with doubly-linked neighbors (`GET /document/{id}`), single
chunk detail views (`GET /{id}`), metrics summary (`GET /metrics`), and purge (`DELETE /document/{id}`).
"""

import uuid
from typing import Any

import structlog
from fastapi import (APIRouter, Depends, Header, HTTPException, Query, Request,
                     status)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.document.repositories import DocumentRepository
from backend.modules.chunking.schemas.chunk import (ChunkCreateRequest,
                                                    ChunkDetailResponse,
                                                    ChunkListResponse,
                                                    ChunkMetricsDTO,
                                                    ChunkResponse,
                                                    StrategyInfoDTO,
                                                    StrategyDiscoveryDTO)
from backend.modules.chunking.schemas.errors import ChunkDomainException
from backend.modules.chunking.services.chunk_service import ChunkingService
from backend.modules.chunking.workers.tasks import \
    process_document_chunking_task

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chunks", tags=["Chunking Foundation"])


def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


def _resolve_tenant(user: Any | None, header_tenant: str | None) -> str:
    if user and getattr(user, "tenant_id", None):
        return user.tenant_id
    return header_tenant or "default_tenant"


@router.get(
    "/strategies",
    response_model=SuccessResponse[StrategyDiscoveryDTO],
    summary="List available chunking strategies",
)
async def list_strategies(request: Request) -> SuccessResponse[StrategyDiscoveryDTO]:
    """Return all registered chunking strategies categorized by status (`ADR-005`)."""
    service = ChunkingService()
    strategies = service.list_strategies()
    return SuccessResponse(data=strategies, metadata=_build_metadata(request))


@router.get(
    "/metrics",
    response_model=SuccessResponse[ChunkMetricsDTO],
    summary="Get chunking summary metrics across tenant namespace",
)
async def get_chunk_metrics(
    request: Request,
    document_id: uuid.UUID | None = Query(
        default=None, description="Optional document ID filter"
    ),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[ChunkMetricsDTO]:
    """Retrieve aggregate KPIs: total chunks, average character/token gauges, and strategy breakdown."""
    tenant_id = _resolve_tenant(user, x_tenant_id)
    service = ChunkingService()
    metrics = await service.get_metrics(
        tenant_id=tenant_id, session=session, document_id=document_id
    )
    return SuccessResponse(data=metrics, metadata=_build_metadata(request))


@router.post(
    "/process/{document_id}",
    response_model=SuccessResponse[dict[str, Any]],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger document chunking",
)
async def process_document_chunking(
    request: Request,
    document_id: uuid.UUID,
    payload: ChunkCreateRequest = ChunkCreateRequest(),
    async_mode: bool = Query(
        default=True, description="Run via background Celery worker if True"
    ),
    version_id: uuid.UUID | None = Query(
        default=None, description="Optional specific version ID to chunk"
    ),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Trigger chunking for a document version using specified or MIME-resolved strategy without embedding (`M1`)."""
    tenant_id = _resolve_tenant(user, x_tenant_id)
    service = ChunkingService()

    # Resolve version ID if not provided
    target_version_id = version_id
    if not target_version_id:
        doc_repo = DocumentRepository()
        doc = await doc_repo.get_by_id(document_id, tenant_id, session)
        if not doc or doc.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found in tenant namespace.",
            )
        if not doc.latest_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no active versions.",
            )
        target_version_id = doc.latest_version_id

    if async_mode:
        # Enqueue Celery background worker
        task = process_document_chunking_task.delay(
            tenant_id=tenant_id,
            document_id=str(document_id),
            version_id=str(target_version_id),
            strategy_override=payload.strategy,
            max_characters=payload.max_characters,
            overlap_characters=payload.overlap_characters,
        )
        return SuccessResponse(
            data={
                "task_id": str(task.id),
                "status": "enqueued",
                "document_id": str(document_id),
                "version_id": str(target_version_id),
                "strategy": payload.strategy or "auto",
            },
            metadata=_build_metadata(request),
        )

    # Synchronous processing
    try:
        chunks, duration_ms = await service.chunk_document_version(
            tenant_id=tenant_id,
            document_id=document_id,
            version_id=target_version_id,
            session=session,
            strategy_override=payload.strategy,
            max_characters=payload.max_characters,
            overlap_characters=payload.overlap_characters,
        )
        return SuccessResponse(
            data={
                "status": "completed",
                "document_id": str(document_id),
                "version_id": str(target_version_id),
                "chunk_count": len(chunks),
                "duration_ms": duration_ms,
            },
            metadata=_build_metadata(request),
        )
    except ChunkDomainException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message)


@router.get(
    "/document/{document_id}",
    response_model=SuccessResponse[ChunkListResponse],
    summary="List paginated chunks for a document",
)
async def list_document_chunks(
    request: Request,
    document_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(
        default=None, description="Filter by version ID"
    ),
    strategy: str | None = Query(default=None, description="Filter by strategy used"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=50, ge=1, le=200, description="Page size"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[ChunkListResponse]:
    """Retrieve paginated chunks with sequence order, character gauges, and doubly-linked pointer IDs (`prev`/`next`)."""
    tenant_id = _resolve_tenant(user, x_tenant_id)
    service = ChunkingService()
    try:
        chunk_list = await service.get_chunks_by_document(
            tenant_id=tenant_id,
            document_id=document_id,
            session=session,
            version_id=version_id,
            strategy_used=strategy,
            page=page,
            size=size,
        )
        return SuccessResponse(data=chunk_list, metadata=_build_metadata(request))
    except ChunkDomainException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message)


@router.get(
    "/{chunk_id}",
    response_model=SuccessResponse[ChunkDetailResponse],
    summary="Get single chunk detail and graph relations",
)
async def get_chunk_detail(
    request: Request,
    chunk_id: uuid.UUID,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[ChunkDetailResponse]:
    """Fetch deep inspection view of a chunk including raw content, section breadcrumbs, and parent/child graph pointers."""
    tenant_id = _resolve_tenant(user, x_tenant_id)
    service = ChunkingService()
    try:
        detail = await service.get_chunk_by_id(
            tenant_id=tenant_id, chunk_id=chunk_id, session=session
        )
        return SuccessResponse(data=detail, metadata=_build_metadata(request))
    except ChunkDomainException as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message)


@router.delete(
    "/document/{document_id}",
    response_model=SuccessResponse[dict[str, Any]],
    summary="Purge chunks for a document namespace",
)
async def delete_document_chunks(
    request: Request,
    document_id: uuid.UUID,
    version_id: uuid.UUID | None = Query(
        default=None, description="Optional version ID to delete specifically"
    ),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    user: Any | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict[str, Any]]:
    """Delete chunks belonging to a document or specific version before re-chunking."""
    tenant_id = _resolve_tenant(user, x_tenant_id)
    service = ChunkingService()
    deleted_count = await service.delete_chunks_by_document(
        tenant_id=tenant_id,
        document_id=document_id,
        session=session,
        version_id=version_id,
    )
    return SuccessResponse(
        data={
            "document_id": str(document_id),
            "version_id": str(version_id) if version_id else "all",
            "deleted_count": deleted_count,
        },
        metadata=_build_metadata(request),
    )
