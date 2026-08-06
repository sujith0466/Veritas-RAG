from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.database import get_db
from backend.core.dependencies.auth import UserContext, require_role
from backend.core.permissions.rbac import Role
from backend.core.events.dispatcher import EventDispatcher
from backend.modules.knowledge_base.schemas.health_score_dto import KnowledgeHealthScoreDTO
from backend.modules.knowledge_base.schemas.knowledge_base_dto import (
    DocumentKnowledgeStatusDTO,
    KnowledgeBaseOverviewDTO,
    VectorParityValidationDTO,
)
from backend.modules.knowledge_base.schemas.reindex_dto import ReindexJobDTO, ReindexRequestDTO
from backend.modules.knowledge_base.schemas.staleness_dto import (
    BulkRemediationRequestDTO,
    BulkRemediationResultDTO,
    StalenessPolicyDTO,
    StalenessReportDTO,
)
from backend.modules.knowledge_base.services.health_score_service import KnowledgeHealthScoreService
from backend.modules.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from backend.modules.knowledge_base.services.staleness_service import StalenessService
from backend.modules.knowledge_base.services.vector_reindex_service import VectorReindexService

router = APIRouter(tags=["Knowledge Base"])


@router.get("/overview", response_model=KnowledgeBaseOverviewDTO)
async def get_overview(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = KnowledgeBaseService(db)
    return await service.get_overview(workspace_id)


@router.get("/documents", response_model=list[DocumentKnowledgeStatusDTO])
async def get_documents(
    workspace_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = KnowledgeBaseService(db)
    dtos, _total = await service.get_documents_status(workspace_id, limit, offset)
    return dtos


@router.get("/vectors/validate", response_model=VectorParityValidationDTO)
async def validate_vector_parity(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = KnowledgeBaseService(db)
    return await service.validate_vector_parity(workspace_id)


@router.get("/health", response_model=KnowledgeHealthScoreDTO)
async def get_health_score(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = KnowledgeHealthScoreService(db)
    return await service.get_workspace_health(workspace_id)


@router.post("/health/recalculate", response_model=KnowledgeHealthScoreDTO)
async def recalculate_health_score(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    # Forces immediate recalculation
    service = KnowledgeHealthScoreService(db)
    return await service.get_workspace_health(workspace_id)


@router.get("/staleness/report", response_model=StalenessReportDTO)
async def get_staleness_report(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    dispatcher = EventDispatcher(db)
    service = StalenessService(db, dispatcher)
    return await service.get_staleness_report(workspace_id)


@router.put("/staleness/policy", response_model=dict)
async def update_staleness_policy(
    workspace_id: UUID,
    policy: StalenessPolicyDTO,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    dispatcher = EventDispatcher(db)
    service = StalenessService(db, dispatcher)
    # Apply policy and trigger immediate evaluation
    await service.evaluate_workspace_staleness(workspace_id, policy)
    return {"message": "Policy updated and evaluation triggered."}


@router.post("/staleness/remediate", response_model=BulkRemediationResultDTO)
async def bulk_remediate_stale_documents(
    workspace_id: UUID,
    request: BulkRemediationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    dispatcher = EventDispatcher(db)
    service = StalenessService(db, dispatcher)
    return await service.execute_bulk_remediation(workspace_id, request)


@router.post("/reindex", response_model=ReindexJobDTO, status_code=status.HTTP_201_CREATED)
async def initiate_reindex(
    workspace_id: UUID,
    request: ReindexRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = VectorReindexService(db)
    try:
        return await service.initiate_reindex(workspace_id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/reindex/{job_id}", response_model=ReindexJobDTO)
async def get_reindex_job(
    workspace_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = VectorReindexService(db)
    job = await service.get_job(workspace_id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/reindex/{job_id}/cancel", response_model=ReindexJobDTO)
async def cancel_reindex_job(
    workspace_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = VectorReindexService(db)
    try:
        return await service.cancel_job(workspace_id, job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/reindex/{job_id}/rollback", response_model=ReindexJobDTO)
async def rollback_reindex_job(
    workspace_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
) -> Any:
    service = VectorReindexService(db)
    try:
        return await service.rollback_job(workspace_id, job_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
