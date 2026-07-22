"""Embedding Pipeline REST API routes (`/api/v1/embeddings`).

Provides endpoints for asynchronous job initiation (`POST /jobs`), job progress monitoring (`GET /jobs/{id}`),
paginated job history (`GET /jobs`), tenant metrics inspection (`GET /metrics`), and provider catalog (`GET /providers`).
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.database import get_db
from backend.modules.embedding.api.dependencies import (get_embedding_service,
                                                        resolve_tenant)
from backend.modules.embedding.providers.factory import \
    EmbeddingProviderFactory
from backend.modules.embedding.schemas.embedding_dto import (
    EmbeddingJobDTO, EmbeddingMetricsDTO, EmbeddingProcessRequestDTO,
    PaginatedJobResponse, ProviderInfoDTO)
from backend.modules.embedding.schemas.errors import EmbeddingDomainException
from backend.modules.embedding.services.embedding_service import \
    EmbeddingService
from backend.modules.embedding.workers.tasks import \
    process_embedding_batch_task

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/embeddings", tags=["Embedding Pipeline"])


def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


@router.post(
    "/jobs",
    response_model=SuccessResponse[EmbeddingJobDTO],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate asynchronous batch embedding job",
)
async def create_embedding_job(
    request_dto: EmbeddingProcessRequestDTO,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    service: EmbeddingService = Depends(get_embedding_service),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[EmbeddingJobDTO]:
    """Trigger vectorization of all unindexed chunks in a document version (`ADR-M2-003`)."""
    try:
        job = await service.initiate_embedding_job(
            tenant_id=tenant_id,
            document_id=request_dto.document_id,
            document_version_id=request_dto.document_version_id,
            provider=request_dto.provider,
            model_name=request_dto.model_name,
            force_reembed=request_dto.force_reembed,
        )
        await session.commit()

        # Dispatch background Celery task
        process_embedding_batch_task.delay(
            str(job.id),
            tenant_id,
            request_dto.batch_size,
            request_dto.force_reembed,
        )

        return SuccessResponse(
            data=EmbeddingJobDTO.model_validate(job),
            metadata=_build_metadata(request),
        )
    except EmbeddingDomainException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("create_embedding_job_unexpected_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.get(
    "/jobs/{job_id}",
    response_model=SuccessResponse[EmbeddingJobDTO],
    summary="Retrieve embedding job status and progress",
)
async def get_embedding_job(
    job_id: uuid.UUID,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    service: EmbeddingService = Depends(get_embedding_service),
) -> SuccessResponse[EmbeddingJobDTO]:
    """Retrieve progress metrics (`processed / total` chunks) for a specific embedding job (`ADR-M2-001`)."""
    job = await service.get_job_status(job_id=job_id, tenant_id=tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Embedding job not found under this tenant namespace.",
        )
    return SuccessResponse(
        data=EmbeddingJobDTO.model_validate(job), metadata=_build_metadata(request)
    )


@router.get(
    "/jobs",
    response_model=SuccessResponse[PaginatedJobResponse],
    summary="List paginated tenant embedding jobs",
)
async def list_embedding_jobs(
    request: Request,
    document_id: uuid.UUID | None = Query(
        default=None, description="Filter by Document ID"
    ),
    job_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(default=20, ge=1, le=100, description="Page size"),
    tenant_id: str = Depends(resolve_tenant),
    service: EmbeddingService = Depends(get_embedding_service),
) -> SuccessResponse[PaginatedJobResponse]:
    """Retrieve paginated embedding job history filtered by tenant namespace (`ADR-M2-001`)."""
    skip = (page - 1) * size
    jobs, total = await service.list_jobs(
        tenant_id=tenant_id,
        document_id=document_id,
        status=job_status,
        skip=skip,
        limit=size,
    )
    pages = (total + size - 1) // size if total > 0 else 1
    items = [EmbeddingJobDTO.model_validate(j) for j in jobs]
    return SuccessResponse(
        data=PaginatedJobResponse(
            items=items, total=total, page=page, size=size, pages=pages
        ),
        metadata=_build_metadata(request),
    )


@router.get(
    "/metrics",
    response_model=SuccessResponse[EmbeddingMetricsDTO],
    summary="Get tenant-level embedding KPIs and token consumption",
)
async def get_embedding_metrics(
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    service: EmbeddingService = Depends(get_embedding_service),
) -> SuccessResponse[EmbeddingMetricsDTO]:
    """Retrieve aggregate token budget usage, total vector inventory, and job distribution (`ADR-M2-001`)."""
    metrics = await service.get_tenant_metrics(tenant_id)
    return SuccessResponse(
        data=EmbeddingMetricsDTO.model_validate(metrics),
        metadata=_build_metadata(request),
    )


@router.get(
    "/providers",
    response_model=SuccessResponse[list[ProviderInfoDTO]],
    summary="List available embedding providers and models",
)
async def list_providers(request: Request) -> SuccessResponse[list[ProviderInfoDTO]]:
    """Retrieve catalog of registered embedding providers, model dimensions, and default configurations (`ADR-M2-001`)."""
    catalog = EmbeddingProviderFactory.list_available_providers()
    return SuccessResponse(data=catalog, metadata=_build_metadata(request))
