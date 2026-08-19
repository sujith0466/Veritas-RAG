
import asyncio
from collections.abc import AsyncGenerator
import json
import time
import uuid

from sqlalchemy import select
from structlog import get_logger

from backend.ai.schemas.wrapper_dto import AIWrapperRequest
from backend.ai.wrapper.service import AIWrapperService
from backend.api.v1.schemas.sse import SSEMessageDTO
from backend.cache.client import get_redis_client
from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.schemas import ChatMessageCreateDTO
from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO
from backend.modules.security.middleware.evaluators import PolicyViolationError
from backend.observability.metrics.prometheus import (
    SSE_ACTIVE_STREAMS,
    SSE_CANCELLATIONS_TOTAL,
    SSE_CHUNKS_PER_STREAM,
    SSE_RECONNECTS_TOTAL,
    SSE_REDIS_BUFFER_HITS_TOTAL,
    SSE_REDIS_BUFFER_MISSES_TOTAL,
    SSE_REPLAYED_CHUNKS_TOTAL,
    SSE_STREAM_DURATION_SECONDS,
)

logger = get_logger(__name__)


_background_tasks = set()

class ChatOrchestrator:
    """Thin adapter orchestrating RAG chat flows via the canonical AIWrapperService."""

    def __init__(
        self,
        chat_repo: ChatRepository,
        ai_wrapper_service: AIWrapperService
    ):
        self.chat_repo = chat_repo
        self.ai_wrapper_service = ai_wrapper_service

    async def stream_chat(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        query: str,
        correlation_id: str,
        workspace_id: uuid.UUID | None = None,
        last_event_id: str | None = None
    ) -> AsyncGenerator[str, None]:
        session_maker = get_session_factory()
        started_at = time.perf_counter()
        settings = get_settings()
        redis = get_redis_client()

        try:
            tenant_uuid = uuid.UUID(tenant_id) if tenant_id else None
            if not tenant_uuid:
                raise ValueError("tenant_id is missing")
        except (ValueError, AttributeError, TypeError):
            err = SSEMessageDTO.error(
                code="UNAUTHORIZED",
                message="Invalid tenant identifier.",
                correlation_id=correlation_id,
                recoverable=False
            )
            yield err.to_sse_string()
            return

        SSE_ACTIVE_STREAMS.inc()
        stream_chunks_count = 0
        redis_key = f"raguard:{tenant_id}:sse:{correlation_id}"

        # 0. SSE Recovery (F8.4)
        if last_event_id and settings.features.enable_sse_recovery:
            SSE_RECONNECTS_TOTAL.inc()
            parts = last_event_id.split(":")
            if len(parts) != 2 or parts[0] != correlation_id:
                err = SSEMessageDTO.error(
                    code="INVALID_CORRELATION",
                    message="The Last-Event-ID does not match the requested correlation ID.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                SSE_ACTIVE_STREAMS.dec()
                return

            last_chunk_index = int(parts[1])
            chunks = await redis.lrange(redis_key, 0, -1)

            if not chunks:
                SSE_REDIS_BUFFER_MISSES_TOTAL.inc()
                err = SSEMessageDTO.error(
                    code="STREAM_EXPIRED",
                    message="Stream replay buffer expired. Please regenerate the request.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                SSE_ACTIVE_STREAMS.dec()
                return

            SSE_REDIS_BUFFER_HITS_TOTAL.inc()
            is_stream_finished = False
            for chunk_bytes in chunks:
                chunk_data = json.loads(chunk_bytes)
                if chunk_data.get("is_final", False):
                    is_stream_finished = True
                if chunk_data["chunk_index"] > last_chunk_index:
                    dto = SSEMessageDTO(
                        id=SSEMessageDTO.format_id(correlation_id, chunk_data["chunk_index"]),
                        event=chunk_data["event_type"],
                        data=json.dumps(chunk_data["payload"])
                    )
                    yield dto.to_sse_string()
                    SSE_REPLAYED_CHUNKS_TOTAL.inc()

            if is_stream_finished:
                # Buffer was complete, we are done
                SSE_ACTIVE_STREAMS.dec()
                return

            # If buffer is incomplete, we fall through and re-execute to resume generation.
            # However, we must skip saving the User Message again, and filter out yielded chunks.
            is_recovering = True
        else:
            is_recovering = False

        # Determine active workspace from session_id
        if workspace_id is None:
            from backend.models.entities.workspace import Workspace
            from backend.models.entities.workspace_member import WorkspaceMember
            try:
                async with session_maker() as session:
                    ws_res = await session.execute(
                        select(Workspace)
                        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
                        .where(WorkspaceMember.user_id == uuid.UUID(user_id))
                        .order_by(Workspace.created_at.asc())
                        .limit(1)
                    )
                    ws = ws_res.scalar_one_or_none()
                    if not ws:
                        err = SSEMessageDTO.error(
                            code="WORKSPACE_REQUIRED",
                            message="User has no active workspaces.",
                            correlation_id=correlation_id,
                            recoverable=False
                        )
                        yield err.to_sse_string()
                        return
                    workspace_id = ws.id
            except Exception as e:
                import logging
                logging.error(f"Failed to determine workspace: {e}")
                err = SSEMessageDTO.error(
                    code="INTERNAL_ERROR",
                    message="Failed to resolve active workspace.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                return

        # 1. Save User Message (Idempotency check: only if not recovering)
        if not is_recovering:
            async with session_maker() as session:
                try:
                    repo = ChatRepository(session)
                    await repo.add_message(
                        session_id=session_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        dto=ChatMessageCreateDTO(
                            role="user",
                            message=query
                        )
                    )
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    import logging
                    logging.error(f"add_message crashed: {error_trace}")
                    yield f"data: {{\"event\": \"error\", \"data\": {{\"message\": \"DB crash: {str(e)}\"}}}}\n\n"
                    return

        # 1.5 Check if knowledge base is still processing
        processing_statuses = [
            DocumentStatus.UPLOADED,
            DocumentStatus.PENDING,
            DocumentStatus.VALIDATING,
            DocumentStatus.EXTRACTING,
            DocumentStatus.OCR,
            DocumentStatus.MANIFEST_GENERATING,
            DocumentStatus.PROCESSED,
            DocumentStatus.CHUNKING,
            DocumentStatus.CHUNKED,
            DocumentStatus.EMBEDDING,
            DocumentStatus.EMBEDDED,
            DocumentStatus.VECTOR_SYNC
        ]

        async with session_maker() as session:
            ready_result = await session.execute(
                select(Document).where(
                    Document.tenant_id == tenant_id,
                    Document.status == DocumentStatus.READY
                ).limit(1)
            )
            has_ready_doc = ready_result.scalar_one_or_none() is not None

            has_processing_doc = False
            if not has_ready_doc:
                proc_result = await session.execute(
                    select(Document).where(
                        Document.tenant_id == tenant_id,
                        Document.status.in_(processing_statuses)
                    ).limit(1)
                )
                has_processing_doc = proc_result.scalar_one_or_none() is not None

            if not has_ready_doc and has_processing_doc:
                msg = "Your knowledge base is currently being prepared. Document processing is still in progress."

                chunk = StreamingGenerationChunkDTO(
                    chunk_index=0,
                    text_delta=msg,
                    is_final=True,
                    is_fully_grounded=True,
                    citations_delta=[],
                    correlation_id=correlation_id
                )

                dto = SSEMessageDTO(
                    id=SSEMessageDTO.format_id(correlation_id, 0),
                    event="chunk",
                    data=chunk.model_dump_json()
                )
                yield dto.to_sse_string()

                repo = ChatRepository(session)
                await repo.add_message(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    dto=ChatMessageCreateDTO(
                        role="assistant",
                        message=msg,
                        citations=[],
                        reliability_score=1.0,
                        metadata_json={"system_message": True}
                    )
                )
                SSE_ACTIVE_STREAMS.dec()
                return

        # 2. Delegate to AIWrapperService
        req = AIWrapperRequest(
            session_id=uuid.UUID(session_id) if '-' in session_id else None,
            workspace_id=workspace_id,
            tenant_id=tenant_uuid,
            query=query,
            stream=True
        )

        full_assistant_text = ""
        final_citations = []
        is_grounded = False
        reliability_score = 1.0
        is_interrupted = False

        try:
            iterator = self.ai_wrapper_service.stream_request(req, uuid.UUID(user_id), correlation_id).__aiter__()

            while True:
                try:
                    # Heartbeat handling (F8.4)
                    timeout = 25.0 if settings.features.enable_sse_heartbeat else None
                    if timeout:
                        chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
                    else:
                        chunk = await iterator.__anext__()

                    if chunk.text_delta:
                        full_assistant_text += chunk.text_delta

                    if chunk.is_final:
                        final_citations = [c.model_dump() for c in chunk.citations_delta]
                        is_grounded = chunk.is_fully_grounded
                        if chunk.wrapper_metadata and "reliability_score" in chunk.wrapper_metadata:
                            reliability_score = chunk.wrapper_metadata["reliability_score"]

                    # F8.3 SSE DTO
                    dto = SSEMessageDTO(
                        id=SSEMessageDTO.format_id(correlation_id, chunk.chunk_index),
                        event="chunk",
                        data=chunk.model_dump_json()
                    )

                    # F8.4 Redis Buffer
                    if settings.features.enable_sse_recovery:
                        chunk_data = json.loads(chunk.model_dump_json())
                        payload = {
                            "chunk_index": chunk.chunk_index,
                            "event_type": "chunk",
                            "payload": chunk_data,
                            "is_final": chunk.is_final,
                        }
                        await redis.rpush(redis_key, json.dumps(payload))
                        # Apply TTL on every chunk to prevent Redis leaks on abort (EP8-018)
                        await redis.expire(redis_key, 300)

                    yield dto.to_sse_string()
                    stream_chunks_count += 1

                    if chunk.is_final:
                        # Emit terminal `event: done` (EP8-014)
                        dto_done = SSEMessageDTO(
                            id=SSEMessageDTO.format_id(correlation_id, chunk.chunk_index + 1),
                            event="done",
                            data="{}"
                        )
                        yield dto_done.to_sse_string()

                except TimeoutError:
                    if settings.features.enable_sse_heartbeat:
                        yield SSEMessageDTO.heartbeat().to_sse_string()
                    continue
                except StopAsyncIteration:
                    break

        except asyncio.CancelledError:
            # F8.6 Graceful Cancellation & Partial Persistence
            logger.warning("Chat stream cancelled by client", session_id=session_id)
            is_interrupted = True
            SSE_CANCELLATIONS_TOTAL.inc()

            # Rethrowing to ensure propagation and cleanup in upstream wrappers/providers
            raise
        except Exception as e:
            logger.error("AI Wrapper stream failed", error=str(e))

            if isinstance(e, PolicyViolationError):
                err = SSEMessageDTO.error(
                    code="POLICY_VIOLATION",
                    message=str(e),
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                return

            if settings.features.enable_timeout_events:
                from backend.observability.metrics.prometheus import SSE_TIMEOUTS_TOTAL
                err_msg = str(e).lower()
                if "timeout" in err_msg or "abort" in err_msg:
                    timeout_type = "ttft_timeout" if "ttft" in err_msg else "inter_token_timeout"
                    SSE_TIMEOUTS_TOTAL.labels(timeout_type=timeout_type).inc()
                    err = SSEMessageDTO.error(
                        code="STREAM_TIMEOUT",
                        message="The AI engine took too long to respond. Please try again.",
                        correlation_id=correlation_id,
                        recoverable=True
                    )
                    yield err.to_sse_string()
                    return

                err = SSEMessageDTO.error(
                    code="INTERNAL_ERROR",
                    message="An internal error occurred during generation.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                return

            raise
        finally:
            SSE_ACTIVE_STREAMS.dec()
            SSE_CHUNKS_PER_STREAM.observe(stream_chunks_count)
            duration_seconds = time.perf_counter() - started_at
            SSE_STREAM_DURATION_SECONDS.observe(duration_seconds)

            # 3. Save Assistant Message (F8.6 Partial Persistence)
            if full_assistant_text or is_interrupted:
                metadata = {
                    "is_fully_grounded": is_grounded,
                    "reliability_score": reliability_score,
                }

                if is_interrupted and settings.features.enable_partial_persistence:
                    metadata.update({
                        "status": "PARTIAL",
                        "is_interrupted": True,
                        "completed": False
                    })

                # Only write to DB if we actually got text or settings enable partial (and text is not empty)
                if (full_assistant_text.strip() and not is_interrupted) or (is_interrupted and settings.features.enable_partial_persistence and full_assistant_text.strip()):
                    async def _persist():
                        async with session_maker() as final_session:
                            repo = ChatRepository(final_session)
                            await repo.add_message(
                                session_id=session_id,
                                tenant_id=tenant_id,
                                user_id=user_id,
                                dto=ChatMessageCreateDTO(
                                    role="assistant",
                                    message=full_assistant_text.strip(),
                                    citations=final_citations,
                                    reliability_score=reliability_score,
                                    metadata_json=metadata
                                )
                            )

                    t = asyncio.create_task(_persist())
                    _background_tasks.add(t)
                    t.add_done_callback(_background_tasks.discard)

            # 4. Analytics
            if not is_interrupted:
                outcome = "SUCCESS" if is_grounded else "UNGROUNDED"
                try:
                    from backend.modules.analytics.models.query_analytics import (
                        QueryAnalyticsRecord,
                    )
                    from backend.observability.metrics import (
                        record_query_metric,
                        record_reliability_metric,
                    )

                    async def _analytics():
                        async with get_session_factory()() as sess:
                            sess.add(
                                QueryAnalyticsRecord(
                                    tenant_id=tenant_id,
                                    correlation_id=correlation_id,
                                    query_text=query,
                                    outcome=outcome,
                                    total_duration_ms=round(duration_seconds * 1000.0, 2),
                                    confidence_score=reliability_score,
                                    hallucination_score=round(1.0 - reliability_score, 4),
                                    reliability_score=reliability_score,
                                    retry_attempts=0,
                                    is_safe_to_serve=is_grounded,
                                )
                            )
                            await sess.commit()

                        record_query_metric(tenant_id, outcome, duration_seconds)
                        record_reliability_metric(reliability_score)

                        # Epic-13 F13.2 Durable Usage Accounting
                        ws_uuid = workspace_id or tenant_uuid
                        if ws_uuid:
                            try:
                                from backend.modules.analytics.services.quota import QuotaGovernor
                                prompt_tok = max(1, len(query.split()) * 2)
                                comp_tok = max(1, len(full_assistant_text.split()) * 2)
                                governor = QuotaGovernor()
                                await governor.record_usage(
                                    workspace_id=ws_uuid,
                                    tokens=prompt_tok + comp_tok,
                                    queries=1,
                                )
                            except Exception as q_exc:
                                logger.warning("Failed recording durable quota usage: %s", q_exc)

                    t = asyncio.create_task(_analytics())
                    _background_tasks.add(t)
                    t.add_done_callback(_background_tasks.discard)
                except Exception as exc:
                    logger.error("Chat analytics background task failed", error=str(exc))
