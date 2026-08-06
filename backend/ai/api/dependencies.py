from fastapi import Depends

from backend.ai.manager import LLMProviderManager
from backend.ai.wrapper.namespace import NamespaceResolver
from backend.ai.wrapper.rate_limit import RateLimiter
from backend.ai.wrapper.service import AIWrapperService
from backend.core.events.dispatcher import EventDispatcher, get_dispatcher
from backend.modules.generation.api.dependencies import get_streaming_generation_service
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.retrieval.api.dependencies import get_retrieval_orchestrator
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator


def get_namespace_resolver() -> NamespaceResolver:
    return NamespaceResolver()


def get_rate_limiter() -> RateLimiter:
    return RateLimiter()


def get_llm_manager() -> LLMProviderManager:
    return LLMProviderManager()


def get_ai_wrapper_service(
    namespace_resolver: NamespaceResolver = Depends(get_namespace_resolver),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    retrieval_orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
    streaming_generation: StreamingGroundedGenerationService = Depends(get_streaming_generation_service),
    event_dispatcher: EventDispatcher = Depends(get_dispatcher),
    llm_manager: LLMProviderManager = Depends(get_llm_manager),
) -> AIWrapperService:
    return AIWrapperService(
        namespace_resolver=namespace_resolver,
        rate_limiter=rate_limiter,
        retrieval_orchestrator=retrieval_orchestrator,
        streaming_generation=streaming_generation,
        event_dispatcher=event_dispatcher,
        llm_manager=llm_manager,
    )
