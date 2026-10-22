"""Generation REST API Routes — Phase 10 / WP-3B."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.modules.analytics.services.pricing import ModelPricingService
from backend.modules.analytics.services.quota import QuotaGovernor
from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTO,
    GenerationRequestDTOv2,
    GroundedAnswerDTO,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.generation_service import GroundedGenerationService
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.security.middleware.ai_policy_middleware import AIPolicyMiddleware

logger = structlog.get_logger(__name__)
router = APIRouter()
_extractor = CitationExtractor()
_prompt_guard = PromptGuard()
_service = GroundedGenerationService(citation_extractor=_extractor, llm_provider=None)
_streaming_service = StreamingGroundedGenerationService(
    citation_extractor=_extractor, prompt_guard=_prompt_guard
)
_policy_middleware = AIPolicyMiddleware()


async def _resolve_workspace_context(
    request_dto: GenerationRequestDTO | GenerationRequestDTOv2,
    current_user: UserContext,
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Resolve (workspace_id, user_id) and verify active workspace membership."""
    ws_uuid: uuid.UUID | None = None
    user_id: uuid.UUID = current_user.id

    # 1. From request DTO (explicit workspace_id or tenant_id)
    dto_ws = getattr(request_dto, "workspace_id", None)
    if dto_ws:
        try:
            ws_uuid = dto_ws if isinstance(dto_ws, uuid.UUID) else uuid.UUID(str(dto_ws))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workspace_id format in request",
            )
    elif getattr(request_dto, "tenant_id", None):
        try:
            ws_uuid = uuid.UUID(str(request_dto.tenant_id))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant_id format in request",
            )

    # 2. If not specified in DTO, fallback to current_user's workspace_id or tenant_id
    if ws_uuid is None:
        user_ws = getattr(current_user, "workspace_id", None)
        if user_ws:
            try:
                ws_uuid = user_ws if isinstance(user_ws, uuid.UUID) else uuid.UUID(str(user_ws))
            except (ValueError, TypeError):
                pass
        if ws_uuid is None and current_user.tenant_id:
            try:
                ws_uuid = uuid.UUID(str(current_user.tenant_id))
            except (ValueError, TypeError):
                pass

    if ws_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing workspace or tenant context for generation",
        )

    # 3. Canonical authorization check: verify caller is an active member
    await get_workspace_member_or_raise(
        workspace_id=ws_uuid,
        current_user=current_user,
        session=session,
    )

    return ws_uuid, user_id


async def _enforce_generation_quota(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    query: str,
    evidence_chunks: list[Any],
    max_answer_tokens: int,
    session: AsyncSession,
) -> int:
    """Validate preflight estimate and enforce hierarchical quota before generation."""
    if not isinstance(max_answer_tokens, int) or max_answer_tokens <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_answer_tokens must be a positive integer",
        )

    est_query_tokens = max(1, len(query.split()) * 2) if query else 1
    est_evidence_tokens = sum(
        max(
            1,
            len(
                str(
                    getattr(c, "content", "")
                    if hasattr(c, "content")
                    else (c.get("content", "") if isinstance(c, dict) else "")
                ).split()
            )
            * 2,
        )
        for c in (evidence_chunks or [])
    )
    preflight_estimate = est_query_tokens + est_evidence_tokens + max_answer_tokens

    governor = QuotaGovernor()
    result = await governor.check_hierarchical_quota(
        workspace_id=workspace_id,
        user_id=user_id,
        requested_tokens=preflight_estimate,
        session=session,
    )
    if not result.is_allowed:
        logger.warning(
            "Generation quota exceeded for workspace %s. Blocked by: %s",
            workspace_id,
            result.blocked_by,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=result.detail or "Workspace token quota exceeded",
            headers={"Retry-After": "3600"},
        )
    return preflight_estimate


@router.post(
    "/generate/grounded",
    response_model=GroundedAnswerDTO,
    summary="Generate grounded answer with citations",
)
async def generate_grounded(
    request: GenerationRequestDTO,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GroundedAnswerDTO:
    """Execute synchronous grounded answer generation ensuring every sentence is cited."""
    ws_uuid, user_id = await _resolve_workspace_context(request, current_user, session)

    await _enforce_generation_quota(
        workspace_id=ws_uuid,
        user_id=user_id,
        query=request.query,
        evidence_chunks=request.evidence_chunks,
        max_answer_tokens=request.max_answer_tokens,
        session=session,
    )

    request.query = await _policy_middleware.evaluate_request(
        tenant_id=ws_uuid,
        workspace_id=ws_uuid,
        query=request.query,
    )

    answer = _service.generate(request)

    # Post-generation usage accounting
    try:
        est_prompt_tokens = max(1, len(request.query.split()) * 2) + sum(
            max(1, len(str(c.get("content", "") if isinstance(c, dict) else "").split()) * 2)
            for c in (request.evidence_chunks or [])
        )
        comp_tokens = max(1, len((answer.answer_text or "").split()) * 2)
        pricing_service = ModelPricingService()
        cost_res = pricing_service.calculate_cost("default", "default", est_prompt_tokens, comp_tokens)

        governor = QuotaGovernor()
        await governor.record_token_usage(
            workspace_id=ws_uuid,
            tenant_id=str(ws_uuid),
            prompt_tokens=est_prompt_tokens,
            completion_tokens=comp_tokens,
            correlation_id=request.correlation_id,
            provider="default",
            model_name="default",
            total_cost_usd=cost_res.total_cost_usd,
            user_id=user_id,
            session=session,
        )
    except Exception as usage_err:
        logger.warning("Failed to record usage for generate_grounded", error=str(usage_err))

    return answer


@router.post("/generate/stream", summary="Stream grounded answer via SSE")
async def generate_stream(
    request: GenerationRequestDTOv2,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Stream grounded answer chunks and live citations using Server-Sent Events (`SSE`)."""
    ws_uuid, user_id = await _resolve_workspace_context(request, current_user, session)

    await _enforce_generation_quota(
        workspace_id=ws_uuid,
        user_id=user_id,
        query=request.query,
        evidence_chunks=request.evidence_chunks,
        max_answer_tokens=request.max_answer_tokens,
        session=session,
    )

    request.query = await _policy_middleware.evaluate_request(
        tenant_id=ws_uuid,
        workspace_id=ws_uuid,
        query=request.query,
    )

    async def sse_generator():
        full_text = ""
        prompt_tokens = max(1, len(request.query.split()) * 2) + sum(
            max(1, len(str(getattr(c, "content", "")).split()) * 2)
            for c in (request.evidence_chunks or [])
        )
        async for chunk in _streaming_service.generate_stream(request):
            if chunk.text_delta:
                full_text += chunk.text_delta
            payload = chunk.model_dump_json()
            yield f"data: {payload}\n\n"

        # Record usage on stream completion
        try:
            comp_tokens = max(1, len(full_text.split()) * 2) if full_text else 1
            pricing_service = ModelPricingService()
            cost_res = pricing_service.calculate_cost("default", "default", prompt_tokens, comp_tokens)

            governor = QuotaGovernor()
            await governor.record_token_usage(
                workspace_id=ws_uuid,
                tenant_id=str(ws_uuid),
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                correlation_id=request.correlation_id,
                provider="default",
                model_name="default",
                total_cost_usd=cost_res.total_cost_usd,
                user_id=user_id,
            )
        except Exception as q_err:
            logger.warning("Failed to record token usage on generation stream complete", error=str(q_err))

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
