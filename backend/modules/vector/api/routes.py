from backend.core.config import get_settings

"""Vector Storage Foundation REST API routes (`/api/v1/vectors`).

Provides endpoints for triggering asynchronous batch vector synchronization (`POST /sync/{version_id}`),
inspecting document synchronization status (`GET /document/{document_id}`), monitoring cluster
and collection health (`GET /health`, `GET /collections`), and purging document points (`DELETE /document/{document_id}`).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.database import get_db
from backend.modules.vector.api.dependencies import (
    get_vector_repository,
    get_vector_service,
    resolve_tenant,
)
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.repositories.vector_repository import VectorMetadataRepository
from backend.modules.vector.schemas.errors import VectorDomainException
from backend.modules.vector.schemas.payload import (
    CollectionDetailDTO,
    PurgeSummaryDTO,
    QdrantClusterHealthDTO,
    VectorIndexMetadataDTO,
    VectorSyncRequestDTO,
)
from backend.modules.vector.services.vector_service import VectorStorageService
from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/vectors", tags=["Vector Storage"])


def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


@router.post(
    "/sync/{version_id}",
    response_model=SuccessResponse[VectorIndexMetadataDTO],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger asynchronous batch synchronization of embeddings into Qdrant",
)
async def sync_document_vectors(
    version_id: uuid.UUID,
    request_dto: VectorSyncRequestDTO,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    repo: VectorMetadataRepository = Depends(get_vector_repository),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[VectorIndexMetadataDTO]:
    """Queue background Celery task to sync staged `ChunkEmbedding` arrays to Qdrant points (`ADR-M3-001`)."""
    try:
        target_col = request_dto.collection_name or get_settings().qdrant.collection_name(tenant_id)
        metadata = await repo.get_or_create_metadata(
            tenant_id=tenant_id,
            document_id=request_dto.document_id,
            document_version_id=version_id,
            collection_name=target_col,
        )
        await session.commit()

        # Dispatch asynchronous Celery ingestion task
        sync_vectors_to_qdrant_task.delay(
            str(request_dto.document_id),
            str(version_id),
            tenant_id,
            request_dto.collection_name,
        )

        return SuccessResponse(
            data=VectorIndexMetadataDTO.model_validate(metadata),
            metadata=_build_metadata(request),
        )
    except VectorDomainException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("sync_document_vectors_api_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate vector synchronization.",
        ) from exc


@router.get(
    "/document/{document_id}",
    response_model=SuccessResponse[list[VectorIndexMetadataDTO]],
    summary="Retrieve synchronization state and point count for a document across collections",
)
async def get_document_sync_status(
    document_id: uuid.UUID,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[list[VectorIndexMetadataDTO]]:
    """Fetch `VectorIndexMetadata` tracking records for a document within the active tenant namespace."""
    stmt = select(VectorIndexMetadata).where(
        VectorIndexMetadata.tenant_id == tenant_id,
        VectorIndexMetadata.document_id == document_id,
        VectorIndexMetadata.is_deleted.is_(False),
    )
    records = (await session.execute(stmt)).scalars().all()
    return SuccessResponse(
        data=[VectorIndexMetadataDTO.model_validate(rec) for rec in records],
        metadata=_build_metadata(request),
    )


@router.get(
    "/health",
    response_model=SuccessResponse[QdrantClusterHealthDTO],
    summary="Inspect Qdrant cluster health, memory usage, and active collections",
)
async def get_qdrant_health(
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    service: VectorStorageService = Depends(get_vector_service),
) -> SuccessResponse[QdrantClusterHealthDTO]:
    """Inspect Qdrant connection readiness and aggregate tenant collection storage metrics (`ADR-M3-001`)."""
    is_healthy = await service.provider.check_connection()
    summary = await service.get_tenant_summary(tenant_id)

    cols = [
        CollectionDetailDTO(
            collection_name=item["collection_name"],
            total_points=item["total_points"],
            indexed_versions_count=item["indexed_versions_count"],
        )
        for item in summary.get("collections", [])
    ]

    health_dto = QdrantClusterHealthDTO(
        status="ONLINE" if is_healthy else "OFFLINE",
        active_collections_count=len(cols),
        total_points_stored=summary.get("total_points_stored", 0),
        collections=cols,
    )
    return SuccessResponse(
        data=health_dto,
        metadata=_build_metadata(request),
    )


@router.get(
    "/collections",
    response_model=SuccessResponse[list[CollectionDetailDTO]],
    summary="List all active tenant vector collections, dimensions, and indexed payload keys",
)
async def list_tenant_collections(
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    service: VectorStorageService = Depends(get_vector_service),
) -> SuccessResponse[list[CollectionDetailDTO]]:
    """List active collections containing points for the requesting tenant (`ADR-004`)."""
    summary = await service.get_tenant_summary(tenant_id)
    cols = [
        CollectionDetailDTO(
            collection_name=item["collection_name"],
            total_points=item["total_points"],
            indexed_versions_count=item["indexed_versions_count"],
        )
        for item in summary.get("collections", [])
    ]
    return SuccessResponse(
        data=cols,
        metadata=_build_metadata(request),
    )


@router.delete(
    "/document/{document_id}",
    response_model=SuccessResponse[PurgeSummaryDTO],
    summary="Purge all vector points for a document from Qdrant (`tenant namespace bound`)",
)
async def delete_document_points(
    document_id: uuid.UUID,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    service: VectorStorageService = Depends(get_vector_service),
    session: AsyncSession = Depends(get_db),
) -> SuccessResponse[PurgeSummaryDTO]:
    """Purge document vector points across all collections and mark metadata as deleted (`ADR-M3-001`)."""
    try:
        purged_count = await service.delete_document_points(document_id, tenant_id)
        await session.commit()
        return SuccessResponse(
            data=PurgeSummaryDTO(
                document_id=document_id,
                tenant_id=tenant_id,
                purged_points_count=purged_count,
            ),
            metadata=_build_metadata(request),
        )
    except VectorDomainException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("delete_document_points_api_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document vector points.",
        ) from exc
