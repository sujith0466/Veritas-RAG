import asyncio
from collections.abc import AsyncGenerator
import time
import uuid

from sqlalchemy import select
import structlog

from backend.ai.manager import LLMProviderManager
from backend.ai.schemas.wrapper_dto import (
    AIWrapperRequest,
    AIWrapperStreamChunk,
)
from backend.ai.wrapper.namespace import NamespaceResolver
from backend.ai.wrapper.rate_limit import RateLimiter
from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType
from backend.core.exceptions import AuthorizationException
from backend.database.engine import get_session_factory
from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus
from backend.modules.generation.schemas.generation_dto import GenerationRequestDTOv2

# (Assuming these exist per the architecture and earlier modules)
from typing import TYPE_CHECKING, Any
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO, SearchRequestDTO
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import WorkspaceMember

if TYPE_CHECKING:
    from backend.modules.query_rewrite.services.rewrite_orchestrator import RewriteOrchestrator
    from backend.modules.reliability.services.reliability_gateway import ReliabilityGateway

logger = structlog.get_logger(__name__)


class WorkspaceValidationError(AuthorizationException):
    def __init__(self, message: str):
        super().__init__(message=message)


class AIWrapperService:
    """Canonical AI orchestration entry point (F8.1)."""

    def __init__(
        self,
        namespace_resolver: NamespaceResolver,
        rate_limiter: RateLimiter,
        retrieval_orchestrator: RetrievalOrchestrator,
        streaming_generation: StreamingGroundedGenerationService,
        event_dispatcher: EventDispatcher,
        llm_manager: LLMProviderManager,
        reliability_gateway: Any | None = None,
        query_rewrite_orchestrator: Any | None = None,
    ):
        self.namespace_resolver = namespace_resolver
        self.rate_limiter = rate_limiter
        self.retrieval_orchestrator = retrieval_orchestrator
        self.streaming_generation = streaming_generation
        self.event_dispatcher = event_dispatcher
        self.llm_manager = llm_manager

        if reliability_gateway is not None:
            self.reliability_gateway = reliability_gateway
        elif retrieval_orchestrator is not None:
            try:
                from backend.modules.reliability.circuit_breaker.engine import (
                    CircuitBreakerEngine,
                )
                from backend.modules.reliability.fallbacks.router import FallbackRouter
                from backend.modules.reliability.fallbacks.zero_result import (
                    ZeroResultRecoverer,
                )
                from backend.modules.reliability.services.reliability_gateway import (
                    ReliabilityGateway,
                )
                from backend.modules.retrieval.api.dependencies import _bm25_provider

                self.reliability_gateway = ReliabilityGateway(
                    orchestrator=retrieval_orchestrator,
                    circuit_breaker=CircuitBreakerEngine(),
                    fallback_router=FallbackRouter(sparse_provider=_bm25_provider),
                    zero_result_recoverer=ZeroResultRecoverer(sparse_provider=_bm25_provider),
                    event_dispatcher=event_dispatcher,
                    target_module="qdrant_hybrid",
                )
            except Exception as e:
                logger.warning("Failed to auto-construct default ReliabilityGateway", error=str(e))
                self.reliability_gateway = None
        else:
            self.reliability_gateway = None

        self.query_rewrite_orchestrator = query_rewrite_orchestrator

        # EP8-004 & EP8-013: Bind the real LLM manager to the generation service
        self.streaming_generation.llm_provider = self.llm_manager

    async def _validate_workspace(self, req: AIWrapperRequest, user_id: uuid.UUID) -> None:
        """Step 2: Workspace Validation (6-check gate)."""

        # 1-4. DB Checks
        session_maker = get_session_factory()
        async with session_maker() as session:
            # Workspace active & features enabled
            workspace = await session.get(Workspace, req.workspace_id)
            from backend.models.entities.workspace import WorkspaceStatus
            if not workspace or str(workspace.id) != str(req.tenant_id) or workspace.status != WorkspaceStatus.ACTIVE.value:
                raise WorkspaceValidationError("Workspace not found or inactive.")

            # EP8-006: AI enabled feature check
            from backend.models.entities.workspace_settings import WorkspaceSettings
            ws_settings = await session.execute(
                select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == req.workspace_id).limit(1)
            )
            settings_obj = ws_settings.scalar_one_or_none()
            if settings_obj and not settings_obj.settings_json.get("ai_enabled", True):
                raise WorkspaceValidationError("AI features disabled for this workspace.")

            # Member check
            member = await session.execute(
                select(WorkspaceMember.id).where(
                    WorkspaceMember.workspace_id == req.workspace_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
            if not member.scalar_one_or_none():
                raise WorkspaceValidationError("User is not a member of this workspace.")

            # Ready KB Check
            docs = await session.execute(
                select(Document.id).where(
                    Document.tenant_id == str(req.tenant_id),
                    Document.status == DocumentStatus.READY
                ).limit(1)
            )
            if not docs.scalar_one_or_none():
                raise WorkspaceValidationError("No READY documents in knowledge base.")

        # 5. Rate Limits (60/min/tenant, 20/min/user)
        await self.rate_limiter.check_rate_limit(req.tenant_id, user_id)

    async def stream_request(
        self, request: AIWrapperRequest, user_id: uuid.UUID, correlation_id: str
    ) -> AsyncGenerator[AIWrapperStreamChunk, None]:
        """Orchestrate the 14-step request lifecycle for streaming."""
        start_time = time.perf_counter()

        # Step 13 (partial): Event
        await self.event_dispatcher.dispatch(
            EventType.AI_WRAPPER_REQUEST_STARTED,
            tenant_id=str(request.tenant_id),
            correlation_id=correlation_id,
            payload={"workspace_id": str(request.workspace_id)}
        )

        try:
            # Step 1 & 2: Validation
            await self._validate_workspace(request, user_id)

            # Step 2.5: AI Policy Enforcement (F8.9)
            from backend.core.config import get_settings
            settings = get_settings()

            if settings.features.enable_ai_policy_engine:
                from backend.modules.security.middleware.ai_policy_middleware import (
                    AIPolicyMiddleware,
                )
                policy_middleware = AIPolicyMiddleware()
                # Modifies query if PII is redacted, blocks if violations occur
                request.query = await policy_middleware.evaluate_request(
                    tenant_id=request.tenant_id,
                    workspace_id=request.workspace_id,
                    query=request.query
                )

            # Step 3: Context injection (history is passed in request.conversation_history)

            # Step 4: Qdrant Namespace Binding
            binding = await self.namespace_resolver.resolve(request.workspace_id, request.tenant_id)

            # Step 5: Query Preprocessing & Contextualization for Retrieval (RET-001)
            retrieval_query = request.query
            if request.conversation_history:
                try:
                    from backend.modules.query_rewrite.schemas.rewrite_dto import (
                        RewriteRequestDTOv2,
                    )
                    history_texts = [
                        t.get("content", "") or t.get("message", "")
                        for t in request.conversation_history
                        if isinstance(t, dict)
                    ]
                    rewrite_req = RewriteRequestDTOv2(
                        original_query=request.query,
                        tenant_id=str(request.tenant_id),
                        conversation_history=[h for h in history_texts if h],
                    )
                    orchestrator = self.query_rewrite_orchestrator
                    if orchestrator is None:
                        from backend.modules.query_rewrite.services.rewrite_orchestrator import (
                            RewriteOrchestrator,
                        )
                        orchestrator = RewriteOrchestrator(llm_provider=self.llm_manager)

                    rewrite_res = orchestrator.rewrite(rewrite_req)
                    if rewrite_res and rewrite_res.rewritten_query:
                        retrieval_query = rewrite_res.rewritten_query
                except Exception as rewrite_exc:
                    logger.warning("Query contextualization skipped", error=str(rewrite_exc))
                    retrieval_query = request.query

            # Step 6: Hybrid Retrieval (Timeout 5s - RET-004)
            search_req = SearchRequestDTO(
                tenant_id=request.tenant_id,
                workspace_id=request.workspace_id,
                query=retrieval_query,
                top_k=5,
            )

            if self.reliability_gateway is not None:
                from backend.modules.reliability.schemas.reliability_dto import SearchOptionsDTO
                search_opts = SearchOptionsDTO(
                    top_k=5,
                    sla_budget_ms=5000.0,
                    enable_fallback=True,
                    enable_zero_result_recovery=True,
                )
                reliable_result = await self.reliability_gateway.execute_reliable_search(
                    query=retrieval_query,
                    tenant_id=str(request.tenant_id),
                    options=search_opts,
                    correlation_id=correlation_id,
                )
                evidence_chunks = []
                for c in (reliable_result.candidates or []):
                    if isinstance(c, RankedEvidenceDTO):
                        evidence_chunks.append(c)
                    else:
                        try:
                            cid = uuid.UUID(str(c.chunk_id))
                        except (ValueError, TypeError, AttributeError):
                            cid = uuid.uuid4()
                        try:
                            did = uuid.UUID(str(c.document_id))
                        except (ValueError, TypeError, AttributeError):
                            did = uuid.uuid4()
                        try:
                            dvid = uuid.UUID(str(c.document_version_id))
                        except (ValueError, TypeError, AttributeError):
                            dvid = uuid.uuid4()
                        evidence_chunks.append(
                            RankedEvidenceDTO(
                                chunk_id=cid,
                                document_id=did,
                                document_version_id=dvid,
                                tenant_id=str(getattr(c, "tenant_id", request.tenant_id)),
                                content=getattr(c, "content", ""),
                                rrf_score=float(getattr(c, "score", 0.0) or 0.0),
                                final_rank=int(getattr(c, "rank", 1) or 1),
                                metadata=getattr(c, "metadata", {}) or {},
                            )
                        )
            else:
                # Ensure consistency by passing tenant_id to the RetrievalOrchestrator
                retrieval_result = await self.retrieval_orchestrator.execute_hybrid_search(
                    options=search_req,
                    tenant_id=str(request.tenant_id),
                    correlation_id=correlation_id,
                )
                evidence_chunks = (
                    retrieval_result.final_evidence
                    if retrieval_result and retrieval_result.final_evidence
                    else []
                )

            await self.event_dispatcher.dispatch(
                EventType.AI_WRAPPER_RETRIEVAL_COMPLETED,
                tenant_id=str(request.tenant_id),
                correlation_id=correlation_id,
                payload={"found": len(evidence_chunks)},
            )

            # Step 7 & 8: Confidence & Retry
            # Handled internally by StreamingGroundedGenerationService in Epic 7 structure,
            # or prepared via evidence_chunks above.

            # Step 9 & 10: Generation
            await self.event_dispatcher.dispatch(
                EventType.AI_WRAPPER_GENERATION_STARTED,
                tenant_id=str(request.tenant_id),
                correlation_id=correlation_id,
                payload={}
            )

            from backend.modules.generation.schemas.generation_dto import PromptGuardrailConfigDTO
            guardrail_cfg = PromptGuardrailConfigDTO(
                custom_system_prompt=request.custom_system_prompt
            )

            gen_request = GenerationRequestDTOv2(
                query=request.query,
                evidence_chunks=evidence_chunks,
                correlation_id=correlation_id,
                tenant_id=str(request.tenant_id),
                conversation_history=request.conversation_history or [],
                stream=True,
                temperature=request.temperature if request.temperature is not None else 0.1,
                guardrail_config=guardrail_cfg,
            )

            # Map legacy chunks to new wrapper chunks
            async for chunk in self.streaming_generation.generate_stream(gen_request):
                chunk_dict = chunk.model_dump()
                chunk_dict.pop("wrapper_metadata", None)
                chunk_dict.pop("namespace_used", None)
                wrapper_meta = {"stage": "generation"}
                if chunk.wrapper_metadata:
                    wrapper_meta.update(chunk.wrapper_metadata)
                wrapper_chunk = AIWrapperStreamChunk(
                    **chunk_dict,
                    namespace_used=binding.collection_name,
                    wrapper_metadata=wrapper_meta
                )
                yield wrapper_chunk

            # Step 11 & 12: Citation & Reliability (Calculated in chunks and accumulated by orchestrator downstream)

            # Step 13: Complete Event
            await self.event_dispatcher.dispatch(
                EventType.AI_WRAPPER_REQUEST_COMPLETED,
                tenant_id=str(request.tenant_id),
                correlation_id=correlation_id,
                payload={"latency_ms": (time.perf_counter() - start_time) * 1000}
            )

        except asyncio.CancelledError:
            await self.event_dispatcher.dispatch(
                EventType.AI_WRAPPER_REQUEST_CANCELLED,
                tenant_id=str(request.tenant_id),
                correlation_id=correlation_id,
                payload={}
            )
            raise
        except Exception as e:
            await self.event_dispatcher.dispatch(
                EventType.AI_WRAPPER_REQUEST_FAILED,
                tenant_id=str(request.tenant_id),
                correlation_id=correlation_id,
                payload={"error": str(e)}
            )
            logger.error("AI Wrapper Request Failed", error=str(e), correlation_id=correlation_id)
            raise
