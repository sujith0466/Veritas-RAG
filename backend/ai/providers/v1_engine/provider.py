from collections.abc import AsyncIterator
import uuid

import structlog

from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.ai.providers.v1_engine.client import V1EngineClient
from backend.ai.schemas.wrapper_dto import AIWrapperRequest
from backend.cache.client import get_redis_client
from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class V1EngineProvider(LLMProvider):
    """
    Implements the LLMProvider interface by delegating to the V1 Engine.
    This allows V1 Engine to participate in the LLMProviderManager failover pool.
    """

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation."""
        # Non-streaming is technically a single stream loop for the V1 Engine
        chunks = []
        final_chunk = None

        # We need to construct a dummy AIWrapperRequest since LLMRequest is missing some fields.
        # Note: In Epic 8, generation is ideally routed via stream() instead, but this must be implemented.
        if not request.workspace_id or not request.tenant_id:
            from backend.ai.providers.v1_engine.exceptions import V1AuthorizationError
            raise V1AuthorizationError("Missing workspace_id or tenant_id in V1Engine request")

        wrapper_req = AIWrapperRequest(
            workspace_id=uuid.UUID(request.workspace_id),
            tenant_id=uuid.UUID(request.tenant_id),
            query=request.prompt,
            guardrail_config={"system_instruction": request.system_instruction},
            stream=False
        )

        async for chunk in V1EngineClient.stream(wrapper_req, correlation_id=str(uuid.uuid4())):
            chunks.append(chunk.text_delta)
            if chunk.is_final:
                final_chunk = chunk

        content = "".join(chunks)

        # Approximate tokens if not provided
        in_tokens = len(request.prompt.split()) * 2
        out_tokens = len(content.split()) * 2

        return LLMResponse(
            content=content,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            model_used=final_chunk.model_used if final_chunk and final_chunk.model_used else "v1_engine_default",
            metadata={"v1_engine": True}
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream generation."""
        if not request.workspace_id or not request.tenant_id:
            from backend.ai.providers.v1_engine.exceptions import V1AuthorizationError
            raise V1AuthorizationError("Missing workspace_id or tenant_id in V1Engine request")

        wrapper_req = AIWrapperRequest(
            workspace_id=uuid.UUID(request.workspace_id),
            tenant_id=uuid.UUID(request.tenant_id),
            query=request.prompt,
            guardrail_config={"system_instruction": request.system_instruction},
            stream=True
        )

        async for chunk in V1EngineClient.stream(wrapper_req, correlation_id=str(uuid.uuid4())):
            yield chunk.text_delta

    async def health_check(self) -> bool:
        """Fetch health from Redis cache populated by background poller, fallback to active probe."""
        settings = get_settings().v1_engine
        if not settings.enabled:
            return False

        redis = get_redis_client()
        status = await redis.get("raguard:v1_engine:health_cache")

        # EP8-007: Fallback active probe if cache is unpopulated
        if not status:
            from backend.ai.providers.v1_engine.client import V1EngineClient
            import httpx
            try:
                # Use the initialized client to preserve mTLS context
                if V1EngineClient._client:
                    res = await V1EngineClient._client.get("/v1/version", timeout=2.0)
                else:
                    async with httpx.AsyncClient(verify=False) as client:
                        res = await client.get(f"{settings.base_url}/v1/version", timeout=2.0)

                if res.status_code == 200:
                    status = b"healthy"
                    await redis.set("raguard:v1_engine:health_cache", "healthy", ex=60)
                else:
                    status = b"unhealthy"
            except Exception as e:
                import structlog
                import traceback
                structlog.get_logger(__name__).error("Health check active probe failed", error=str(e), trace=traceback.format_exc())
                status = b"unhealthy"

        # Handle both bytes and str returns from Redis mock/actual clients
        if isinstance(status, bytes):
            return status.decode("utf-8") == "healthy"
        return status == "healthy"
