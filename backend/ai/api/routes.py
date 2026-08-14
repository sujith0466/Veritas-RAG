import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from backend.ai.api.dependencies import (
    get_ai_wrapper_service,
    get_llm_manager,
    get_namespace_resolver,
)
from backend.ai.manager import LLMProviderManager
from backend.ai.schemas.wrapper_dto import AIWrapperRequest, AIWrapperResponse
from backend.ai.wrapper.namespace import NamespaceResolver
from backend.ai.wrapper.service import AIWrapperService
from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user, require_role
from backend.core.permissions.rbac import Role

router = APIRouter(prefix="/ai", tags=["AI Platform Wrapper"])

def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)

@router.post("/stream")
async def stream_ai_request(
    dto: AIWrapperRequest,
    request: Request,
    service: AIWrapperService = Depends(get_ai_wrapper_service),
    user: UserContext = Depends(get_current_user)
):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # Enforce tenant_id from JWT
    dto.tenant_id = user.tenant_id

    async def _stream_generator():
        async for chunk in service.stream_request(dto, user.id, correlation_id):
            yield f"data: {chunk.model_dump_json()}\n\n"

    return StreamingResponse(
        _stream_generator(),
        media_type="text/event-stream"
    )

@router.post("/generate", response_model=SuccessResponse[AIWrapperResponse])
async def generate_ai_request(
    dto: AIWrapperRequest,
    request: Request,
    service: AIWrapperService = Depends(get_ai_wrapper_service),
    user: UserContext = Depends(get_current_user)
):
    # This falls back to stream and accumulates it for non-streaming consumers
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    dto.tenant_id = user.tenant_id
    dto.stream = False

    content = ""
    citations = []
    reliability = 0.0
    grounded = False

    async for chunk in service.stream_request(dto, user.id, correlation_id):
        content += chunk.text_delta
        if chunk.is_final:
            citations = [c.model_dump() for c in chunk.citations_delta]

            if chunk.wrapper_metadata and "reliability_score" in chunk.wrapper_metadata:
                reliability = chunk.wrapper_metadata["reliability_score"]
            else:
                reliability = 0.5  # Fallback if uncalculated

            grounded = chunk.is_fully_grounded

    resp = AIWrapperResponse(
        content=content,
        is_fully_grounded=grounded,
        reliability_score=reliability,
        citations=citations
    )

    return SuccessResponse[AIWrapperResponse](
        data=resp,
        metadata=_build_metadata(request)
    )

@router.get("/health")
async def ai_health(
    request: Request,
    manager: LLMProviderManager = Depends(get_llm_manager),
    user: UserContext = Depends(require_role(Role.PLATFORM_ADMIN))
):
    health_data = await manager.detailed_health_check()
    return SuccessResponse(
        data=health_data,
        metadata=_build_metadata(request)
    )

@router.get("/capabilities")
async def ai_capabilities(
    request: Request,
    user: UserContext = Depends(get_current_user)
):
    from backend.core.config import get_settings
    settings = get_settings()
    data = {
        "v1_engine_enabled": settings.v1_engine.enabled,
        "streaming_supported": True,
        "models": settings.ai.priority_list
    }
    return SuccessResponse(data=data, metadata=_build_metadata(request))

@router.delete("/cache/namespace", status_code=status.HTTP_204_NO_CONTENT)
async def delete_namespace_cache(
    user: UserContext = Depends(require_role(Role.PLATFORM_ADMIN)),
    resolver: NamespaceResolver = Depends(get_namespace_resolver)
):
    cache_key = f"raguard:{user.tenant_id}:namespace:binding"
    await resolver.redis.delete(cache_key)
