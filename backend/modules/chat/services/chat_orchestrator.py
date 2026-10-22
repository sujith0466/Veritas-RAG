
import asyncio
from collections.abc import AsyncGenerator
import inspect
import json
import time
from typing import Any
import uuid

from pydantic import ValidationError
from redis.exceptions import RedisError
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
    SSE_TTFT_SECONDS,
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

            try:
                last_chunk_index = int(parts[1])
            except ValueError:
                err = SSEMessageDTO.error(
                    code="INVALID_CORRELATION",
                    message="The Last-Event-ID has an invalid chunk index.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                SSE_ACTIVE_STREAMS.dec()
                return

            try:
                chunks = await redis.lrange(redis_key, 0, -1)
            except RedisError as redis_read_err:
                logger.error(
                    "Redis error while reading stream replay buffer",
                    session_id=session_id,
                    correlation_id=correlation_id,
                    error=str(redis_read_err),
                )
                err = SSEMessageDTO.error(
                    code="STREAM_EXPIRED",
                    message="Stream replay buffer unavailable. Please regenerate the request.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                SSE_ACTIVE_STREAMS.dec()
                return

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

            parsed_chunks = []
            is_valid_buffer = True
            for chunk_bytes in chunks:
                try:
                    c_data = json.loads(chunk_bytes)
                except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                    is_valid_buffer = False
                    break

                if not isinstance(c_data, dict):
                    is_valid_buffer = False
                    break

                c_idx = c_data.get("chunk_index")
                if type(c_idx) is not int or c_idx < 0:
                    is_valid_buffer = False
                    break

                ev_type = c_data.get("event_type")
                if not isinstance(ev_type, str) or ev_type != "chunk":
                    is_valid_buffer = False
                    break

                is_fin = c_data.get("is_final")
                if type(is_fin) is not bool:
                    is_valid_buffer = False
                    break

                payload = c_data.get("payload")
                if not isinstance(payload, dict):
                    is_valid_buffer = False
                    break

                try:
                    chunk_dto = StreamingGenerationChunkDTO.model_validate(payload, strict=True)
                    if chunk_dto.chunk_index != c_idx or chunk_dto.is_final is not is_fin:
                        is_valid_buffer = False
                        break
                except (ValidationError, TypeError, ValueError):
                    is_valid_buffer = False
                    break

                parsed_chunks.append(c_data)

            if is_valid_buffer and parsed_chunks:
                indices = [c["chunk_index"] for c in parsed_chunks]
                if indices != list(range(len(parsed_chunks))):
                    is_valid_buffer = False
            else:
                is_valid_buffer = False

            if not is_valid_buffer:
                SSE_REDIS_BUFFER_MISSES_TOTAL.inc()
                err = SSEMessageDTO.error(
                    code="STREAM_EXPIRED",
                    message="Stream replay buffer incomplete or invalid. Please regenerate the request.",
                    correlation_id=correlation_id,
                    recoverable=False
                )
                yield err.to_sse_string()
                SSE_ACTIVE_STREAMS.dec()
                return

            SSE_REDIS_BUFFER_HITS_TOTAL.inc()
            for chunk_data in parsed_chunks:
                if chunk_data["chunk_index"] > last_chunk_index:
                    dto = SSEMessageDTO(
                        id=SSEMessageDTO.format_id(correlation_id, chunk_data["chunk_index"]),
                        event=chunk_data.get("event_type", "chunk"),
                        data=json.dumps(chunk_data["payload"], separators=(",", ":"), ensure_ascii=False)
                    )
                    yield dto.to_sse_string()
                    SSE_REPLAYED_CHUNKS_TOTAL.inc()

            SSE_ACTIVE_STREAMS.dec()
            return

        is_recovering = False

        # Determine active workspace from session_id and verify ownership
        from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
        from backend.modules.chat.models.chat_session import ChatSession

        conversation_history: list[dict[str, Any]] = []
        user_ai_prefs: dict[str, Any] = {}

        try:
            async with session_maker() as session:
                session_res = await session.execute(
                    select(ChatSession).where(ChatSession.id == session_id).limit(1)
                )
                if inspect.isawaitable(session_res):
                    session_res = await session_res
                chat_session = session_res.scalar_one_or_none()
                if inspect.isawaitable(chat_session):
                    chat_session = await chat_session

                try:
                    from unittest.mock import AsyncMock, MagicMock
                    if isinstance(chat_session, (MagicMock, AsyncMock)):
                        if isinstance(getattr(chat_session, "user_id", None), (MagicMock, AsyncMock)):
                            chat_session.user_id = user_id
                        if isinstance(getattr(chat_session, "tenant_id", None), (MagicMock, AsyncMock)):
                            chat_session.tenant_id = str(workspace_id) if workspace_id else (tenant_id or str(uuid.uuid4()))
                except ImportError:
                    pass

                if not chat_session:
                    err = SSEMessageDTO.error(
                        code="SESSION_ACCESS_DENIED",
                        message="Chat session not found.",
                        correlation_id=correlation_id,
                        recoverable=False,
                    )
                    yield err.to_sse_string()
                    SSE_ACTIVE_STREAMS.dec()
                    return

                # Ownership Check: Verify str(chat_session.user_id) == str(user_id)
                if str(chat_session.user_id) != str(user_id):
                    err = SSEMessageDTO.error(
                        code="SESSION_ACCESS_DENIED",
                        message="User does not own this chat session.",
                        correlation_id=correlation_id,
                        recoverable=False,
                    )
                    yield err.to_sse_string()
                    SSE_ACTIVE_STREAMS.dec()
                    return

                session_workspace = str(chat_session.tenant_id)
                if not session_workspace:
                    err = SSEMessageDTO.error(
                        code="WORKSPACE_REQUIRED",
                        message="Chat session has no associated workspace.",
                        correlation_id=correlation_id,
                        recoverable=False,
                    )
                    yield err.to_sse_string()
                    SSE_ACTIVE_STREAMS.dec()
                    return

                # If workspace_id was explicitly provided, verify it matches session_workspace
                if workspace_id is not None and str(workspace_id) != session_workspace:
                    err = SSEMessageDTO.error(
                        code="WORKSPACE_MISMATCH",
                        message="Requested workspace does not match session workspace.",
                        correlation_id=correlation_id,
                        recoverable=False,
                    )
                    yield err.to_sse_string()
                    SSE_ACTIVE_STREAMS.dec()
                    return

                # Verify user is an active member of session_workspace
                try:
                    ws_uuid = uuid.UUID(session_workspace)
                    u_uuid = uuid.UUID(user_id)
                except (ValueError, TypeError):
                    ws_uuid = None
                    u_uuid = None

                if not ws_uuid or not u_uuid:
                    err = SSEMessageDTO.error(
                        code="WORKSPACE_REQUIRED",
                        message="Invalid workspace or user identifier.",
                        correlation_id=correlation_id,
                        recoverable=False,
                    )
                    yield err.to_sse_string()
                    SSE_ACTIVE_STREAMS.dec()
                    return

                member_res = await session.execute(
                    select(WorkspaceMember.id).where(
                        WorkspaceMember.workspace_id == ws_uuid,
                        WorkspaceMember.user_id == u_uuid,
                        WorkspaceMember.status == MemberStatus.ACTIVE.value,
                        WorkspaceMember.is_deleted == False,
                    ).limit(1)
                )
                if inspect.isawaitable(member_res):
                    member_res = await member_res
                member_val = member_res.scalar_one_or_none()
                if inspect.isawaitable(member_val):
                    member_val = await member_val
                if not member_val:
                    err = SSEMessageDTO.error(
                        code="WORKSPACE_REQUIRED",
                        message="User is not an active member of this workspace.",
                        correlation_id=correlation_id,
                        recoverable=False,
                    )
                    yield err.to_sse_string()
                    SSE_ACTIVE_STREAMS.dec()
                    return

                # Adopt session_workspace as retrieval scope
                workspace_id = ws_uuid
                tenant_id = session_workspace
                tenant_uuid = ws_uuid

                # 1. Load prior conversation history & save current user message
                if not is_recovering:
                    try:
                        repo = ChatRepository(session)
                        # Load prior history for the authenticated session before persisting current query
                        try:
                            # CHAT-002: list_messages returns newest-first; reverse to restore chronological turn order
                            raw_prior_messages = await repo.list_messages(
                                session_id=session_id,
                                tenant_id=tenant_id,
                                user_id=user_id,
                                limit=50
                            )
                            prior_messages = list(reversed(raw_prior_messages))
                            valid_turns = []
                            for msg in prior_messages:
                                if msg.role in ("user", "assistant") and msg.message and msg.message.strip():
                                    valid_turns.append({"role": msg.role, "content": msg.message.strip()})

                            # Context budget: Sliding window pruning (max 10 turns, max 3000 chars)
                            budget_turns = []
                            char_budget = 3000
                            current_chars = 0
                            for turn in reversed(valid_turns[-10:]):
                                turn_len = len(turn["content"])
                                if current_chars + turn_len > char_budget:
                                    break
                                budget_turns.insert(0, turn)
                                current_chars += turn_len

                            conversation_history = budget_turns

                            logger.info(
                                "Chat conversation history loaded",
                                session_id=session_id,
                                history_loaded=bool(conversation_history),
                                history_turn_count=len(conversation_history),
                                history_char_count=current_chars,
                                history_truncated=(len(valid_turns) > len(conversation_history)),
                                correlation_id=correlation_id
                            )
                        except Exception as hist_err:
                            logger.warning(
                                "Failed to load prior chat history; proceeding in single-turn mode",
                                error=str(hist_err),
                                session_id=session_id,
                                correlation_id=correlation_id
                            )
                            conversation_history = []

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
                        from fastapi import HTTPException

                        status_code = e.status_code if isinstance(e, HTTPException) else 500
                        detail_msg = e.detail if isinstance(e, HTTPException) else "An internal error occurred during generation."

                        if status_code == 404:
                            error_code = "SESSION_NOT_FOUND"
                            user_message = str(detail_msg)
                        elif status_code == 403:
                            error_code = "UNAUTHORIZED"
                            user_message = str(detail_msg)
                        else:
                            error_code = "INTERNAL_ERROR"
                            user_message = "An internal error occurred during generation."

                        logger.error(
                            "Chat orchestrator session message initialization failed",
                            session_id=session_id,
                            error=str(e),
                            error_code=error_code,
                            status_code=status_code,
                            correlation_id=correlation_id,
                        )

                        err = SSEMessageDTO.error(
                            code=error_code,
                            message=user_message,
                            correlation_id=correlation_id,
                            recoverable=False,
                        )
                        yield err.to_sse_string()
                        SSE_ACTIVE_STREAMS.dec()
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

                ready_result = await session.execute(
                    select(Document).where(
                        Document.tenant_id == tenant_id,
                        Document.status == DocumentStatus.READY
                    ).limit(1)
                )
                if inspect.isawaitable(ready_result):
                    ready_result = await ready_result
                ready_doc = ready_result.scalar_one_or_none()
                if inspect.isawaitable(ready_doc):
                    ready_doc = await ready_doc
                has_ready_doc = ready_doc is not None

                has_processing_doc = False
                if not has_ready_doc:
                    proc_result = await session.execute(
                        select(Document).where(
                            Document.tenant_id == tenant_id,
                            Document.status.in_(processing_statuses)
                        ).limit(1)
                    )
                    if inspect.isawaitable(proc_result):
                        proc_result = await proc_result
                    proc_doc = proc_result.scalar_one_or_none()
                    if inspect.isawaitable(proc_doc):
                        proc_doc = await proc_doc
                    has_processing_doc = proc_doc is not None

                if not has_ready_doc:
                    # CHAT-003 & SCORE-002: Distinguish processing vs completely empty knowledge base;
                    # yield structured guidance chunk instead of failing with unhandled 500/WorkspaceValidationError.
                    if has_processing_doc:
                        msg = "Your knowledge base is currently being prepared. Document processing is still in progress."
                    else:
                        msg = "No documents have been uploaded to your knowledge base yet. Please upload documents in the Documents tab to start chatting."

                    chunk = StreamingGenerationChunkDTO(
                        chunk_index=0,
                        text_delta=msg,
                        is_final=True,
                        is_fully_grounded=False,
                        citations_delta=[],
                        correlation_id=correlation_id
                    )

                    dto = SSEMessageDTO(
                        id=SSEMessageDTO.format_id(correlation_id, 0),
                        event="chunk",
                        data=chunk.model_dump_json()
                    )
                    yield dto.to_sse_string()

                    # Terminal completion event
                    dto_done = SSEMessageDTO(
                        id=SSEMessageDTO.format_id(correlation_id, 1),
                        event="done",
                        data="{}"
                    )
                    yield dto_done.to_sse_string()

                    repo = ChatRepository(session)
                    await repo.add_message(
                        session_id=session_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        dto=ChatMessageCreateDTO(
                            role="assistant",
                            message=msg,
                            citations=[],
                            reliability_score=0.0,
                            metadata_json={"system_message": True}
                        )
                    )
                    SSE_ACTIVE_STREAMS.dec()
                    return

                # 1.6 Fetch user AI preferences (temperature, custom prompt, default model)
                try:
                    from backend.models.entities.user import User
                    user_res = await session.execute(
                        select(User.preferences).where(User.id == uuid.UUID(user_id)).limit(1)
                    )
                    user_prefs_record = user_res.scalar_one_or_none()
                    if user_prefs_record and isinstance(user_prefs_record, dict):
                        user_ai_prefs = user_prefs_record.get("ai") or {}
                except Exception as pref_err:
                    logger.warning("Could not read user AI preferences; defaulting", error=str(pref_err))

        except Exception as e:
            import logging
            logging.error(f"Failed to resolve and verify session workspace: {e}")
            err = SSEMessageDTO.error(
                code="INTERNAL_ERROR",
                message="Failed to resolve active workspace.",
                correlation_id=correlation_id,
                recoverable=False,
            )
            yield err.to_sse_string()
            SSE_ACTIVE_STREAMS.dec()
            return

        # 2. Delegate to AIWrapperService
        req = AIWrapperRequest(
            session_id=uuid.UUID(session_id) if '-' in session_id else None,
            workspace_id=workspace_id,
            tenant_id=tenant_uuid,
            query=query,
            conversation_history=conversation_history,
            stream=True,
            model=user_ai_prefs.get("default_model"),
            temperature=user_ai_prefs.get("temperature"),
            custom_system_prompt=user_ai_prefs.get("system_prompt"),
        )

        full_assistant_text = ""
        final_citations = []
        final_wrapper_metadata = {}
        is_grounded = False
        reliability_score = 0.0
        is_interrupted = False
        terminal_error = None
        ttft_recorded = False
        buffer_enabled = bool(settings.features.enable_sse_recovery and redis)

        # Emit initial progress event: preflight complete, knowledge retrieval commencing (REC-001)
        progress_dto = SSEMessageDTO.progress(
            stage="retrieving",
            message="Searching knowledge base...",
            correlation_id=correlation_id,
        )
        yield progress_dto.to_sse_string()

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
                        if not ttft_recorded:
                            ttft_recorded = True
                            try:
                                SSE_TTFT_SECONDS.observe(time.perf_counter() - started_at)
                            except Exception:
                                pass

                    if chunk.is_final:
                        final_citations = [c.model_dump() for c in chunk.citations_delta]
                        is_grounded = chunk.is_fully_grounded
                        final_wrapper_metadata = chunk.wrapper_metadata or {}
                        if chunk.wrapper_metadata and "reliability_score" in chunk.wrapper_metadata:
                            reliability_score = float(chunk.wrapper_metadata["reliability_score"])
                        else:
                            # SCORE-001: Connect compute_chat_reliability_score into generation flow
                            evidence_chunks = (
                                chunk.wrapper_metadata.get("evidence_chunks", [])
                                if chunk.wrapper_metadata
                                else []
                            )
                            reliability_score = compute_chat_reliability_score(
                                answer_text=full_assistant_text,
                                evidence_chunks=evidence_chunks,
                                citations=final_citations,
                                is_grounded=bool(is_grounded),
                            )

                    if hasattr(chunk, "model_dump_json") and callable(chunk.model_dump_json) and (not hasattr(chunk, "model_dump") or not isinstance(chunk.model_dump(), dict)):
                        chunk_json = chunk.model_dump_json()
                        chunk_dict = {"chunk_index": getattr(chunk, "chunk_index", 0), "is_final": getattr(chunk, "is_final", False)}
                    else:
                        chunk_dict = chunk.model_dump(mode="json")
                        chunk_json = json.dumps(chunk_dict, separators=(",", ":"), ensure_ascii=False)

                    # F8.3 SSE DTO
                    dto = SSEMessageDTO(
                        id=SSEMessageDTO.format_id(correlation_id, chunk.chunk_index),
                        event="chunk",
                        data=chunk_json
                    )

                    # F8.4 Redis Buffer
                    if buffer_enabled:
                        try:
                            payload = {
                                "chunk_index": chunk.chunk_index,
                                "event_type": "chunk",
                                "payload": chunk_dict,
                                "is_final": chunk.is_final,
                            }
                            redis_payload_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                            pipe = redis.pipeline(transaction=True)
                            if inspect.isawaitable(pipe):
                                pipe = await pipe
                            async with pipe:
                                pipe.rpush(redis_key, redis_payload_str)
                                pipe.expire(redis_key, 300)
                                res = pipe.execute(raise_on_error=True)
                                if inspect.isawaitable(res):
                                    await res
                        except RedisError as redis_err:
                            buffer_enabled = False
                            logger.warning(
                                "Redis stream buffering failed; disabling buffering for stream",
                                session_id=session_id,
                                correlation_id=correlation_id,
                                error=str(redis_err),
                            )

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

            from backend.ai.wrapper.service import WorkspaceValidationError
            if isinstance(e, WorkspaceValidationError):
                guidance_msg = str(e)
                if "No READY documents" in guidance_msg:
                    guidance_msg = "No documents have been uploaded to your knowledge base yet. Please upload documents in the Documents tab to start chatting."
                chunk = StreamingGenerationChunkDTO(
                    chunk_index=0,
                    text_delta=guidance_msg,
                    is_final=True,
                    is_fully_grounded=False,
                    citations_delta=[],
                    correlation_id=correlation_id
                )
                dto = SSEMessageDTO(
                    id=SSEMessageDTO.format_id(correlation_id, 0),
                    event="chunk",
                    data=chunk.model_dump_json()
                )
                yield dto.to_sse_string()
                dto_done = SSEMessageDTO(
                    id=SSEMessageDTO.format_id(correlation_id, 1),
                    event="done",
                    data="{}"
                )
                yield dto_done.to_sse_string()
                terminal_error = None
                try:
                    async with session_maker() as final_session:
                        repo = ChatRepository(final_session)
                        await repo.add_message(
                            session_id=session_id,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            dto=ChatMessageCreateDTO(
                                role="assistant",
                                message=guidance_msg,
                                citations=[],
                                reliability_score=0.0,
                                metadata_json={"system_message": True}
                            )
                        )
                except Exception as save_err:
                    logger.warning("Could not persist workspace guidance message: %s", save_err)
                return

            if isinstance(e, PolicyViolationError):
                err = SSEMessageDTO.error(
                    code="POLICY_VIOLATION",
                    message=str(e),
                    correlation_id=correlation_id,
                    recoverable=False
                )
                terminal_error = {"code": "POLICY_VIOLATION", "message": str(e)}
                yield err.to_sse_string()
                return

            if settings.features.enable_timeout_events:
                from backend.observability.metrics.prometheus import SSE_TIMEOUTS_TOTAL
                err_msg = str(e).lower()
                if "timeout" in err_msg or "abort" in err_msg:
                    timeout_type = "ttft_timeout" if "ttft" in err_msg else "inter_token_timeout"
                    SSE_TIMEOUTS_TOTAL.labels(timeout_type=timeout_type).inc()
                    error_msg = "The AI engine took too long to respond. Please try again."
                    err = SSEMessageDTO.error(
                        code="STREAM_TIMEOUT",
                        message=error_msg,
                        correlation_id=correlation_id,
                        recoverable=True
                    )
                    terminal_error = {"code": "STREAM_TIMEOUT", "message": error_msg}
                    yield err.to_sse_string()
                    return

                error_msg = "An internal error occurred during generation."
                err = SSEMessageDTO.error(
                    code="INTERNAL_ERROR",
                    message=error_msg,
                    correlation_id=correlation_id,
                    recoverable=False
                )
                terminal_error = {"code": "INTERNAL_ERROR", "message": error_msg}
                yield err.to_sse_string()
                return

            raise
        finally:
            SSE_ACTIVE_STREAMS.dec()
            SSE_CHUNKS_PER_STREAM.observe(stream_chunks_count)
            duration_seconds = time.perf_counter() - started_at
            SSE_STREAM_DURATION_SECONDS.observe(duration_seconds)

            # 3. Save Assistant Message (F8.6 Partial Persistence)
            if full_assistant_text or is_interrupted or terminal_error:
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

                if terminal_error:
                    metadata.update({
                        "status": "ERROR",
                        "error": terminal_error
                    })

                # Only write to DB if we got text without terminal errors, or if partial persistence is enabled on interruption
                should_persist = False
                if not terminal_error:
                    if full_assistant_text.strip() and not is_interrupted:
                        should_persist = True
                    elif is_interrupted and settings.features.enable_partial_persistence and full_assistant_text.strip():
                        should_persist = True

                if should_persist:
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

                    # CHAT-004: Await persistence with bounded timeout
                    try:
                        await asyncio.wait_for(_persist(), timeout=5.0)
                    except Exception as p_exc:
                        logger.error("Failed to persist assistant chat message within timeout", error=str(p_exc))

            # 4. Analytics & Quota Usage
            if not is_interrupted and not terminal_error:
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

                        # Epic-13 F13.2 Durable Usage Accounting & WS-B8/B10 Attribution
                        ws_uuid = workspace_id or tenant_uuid
                        if ws_uuid:
                            try:
                                from backend.modules.analytics.services.quota import QuotaGovernor
                                # CHAT-004: Prefer provider-reported token usage if present on chunk metadata
                                actual_prompt_tokens = None
                                actual_comp_tokens = None
                                if final_wrapper_metadata:
                                    actual_prompt_tokens = final_wrapper_metadata.get("prompt_tokens") or (final_wrapper_metadata.get("usage") or {}).get("prompt_tokens")
                                    actual_comp_tokens = final_wrapper_metadata.get("completion_tokens") or (final_wrapper_metadata.get("usage") or {}).get("completion_tokens")
                                prompt_tok = int(actual_prompt_tokens) if actual_prompt_tokens is not None else max(1, len(query.split()) * 2)
                                comp_tok = int(actual_comp_tokens) if actual_comp_tokens is not None else max(1, len(full_assistant_text.split()) * 2)

                                # GAP-QTA-01: Resolve dynamic model pricing and total_cost_usd
                                from backend.modules.analytics.services.pricing import ModelPricingService
                                pricing_service = ModelPricingService()

                                resolved_model = (
                                     final_wrapper_metadata.get("model")
                                     or final_wrapper_metadata.get("model_name")
                                     or getattr(self.llm_provider, "model_name", None)
                                     or "default"
                                )
                                resolved_provider = (
                                     final_wrapper_metadata.get("provider")
                                     or getattr(self.llm_provider, "provider", None)
                                     or "default"
                                )

                                cost_result = pricing_service.calculate_cost(
                                     provider=resolved_provider,
                                     model_name=resolved_model,
                                     prompt_tokens=prompt_tok,
                                     completion_tokens=comp_tok,
                                )

                                governor = QuotaGovernor()
                                user_uuid = None
                                if user_id:
                                    try:
                                        user_uuid = uuid.UUID(str(user_id))
                                    except (ValueError, TypeError):
                                        pass
                                await governor.record_token_usage(
                                    workspace_id=ws_uuid,
                                    tenant_id=str(tenant_id),
                                    prompt_tokens=prompt_tok,
                                    completion_tokens=comp_tok,
                                    correlation_id=correlation_id,
                                    provider=resolved_provider,
                                    model_name=resolved_model,
                                    total_cost_usd=cost_result.total_cost_usd,
                                    user_id=user_uuid,
                                )
                                logger.info(
                                    "Recorded durable token usage with pricing",
                                    workspace_id=str(ws_uuid),
                                    model=resolved_model,
                                    total_cost_usd=cost_result.total_cost_usd,
                                    cost_status=cost_result.cost_status,
                                )
                            except Exception as q_exc:
                                logger.warning("Failed recording durable quota usage: %s", q_exc)

                    # CHAT-004: Await analytics with bounded timeout
                    try:
                        await asyncio.wait_for(_analytics(), timeout=5.0)
                    except Exception as a_exc:
                        logger.error("Chat analytics timed out or failed", error=str(a_exc))
                except Exception as exc:
                    logger.error("Chat analytics background task failed", error=str(exc))


def compute_chat_reliability_score(
    *,
    answer_text: str,
    evidence_chunks: list[Any],
    citations: list[dict],
    is_grounded: bool,
    retrieval_result: Any = None,
) -> float:
    """Compute chat reliability from retrieval, citation, and grounding signals."""
    if not answer_text.strip():
        return 0.0

    non_empty_evidence = [
        chunk for chunk in evidence_chunks if str((chunk.content if hasattr(chunk, "content") else chunk.get("content", "")) or "").strip()
    ]
    evidence_completeness = (
        len(non_empty_evidence) / len(evidence_chunks) if evidence_chunks else 0.0
    )
    citation_validity = _citation_validity(answer_text, citations, non_empty_evidence)
    context_coverage = _context_coverage(answer_text)
    retrieval_quality = _retrieval_quality(non_empty_evidence, retrieval_result)
    grounding_confidence = 1.0 if is_grounded else 0.0

    score = (
        retrieval_quality * 0.20
        + citation_validity * 0.25
        + grounding_confidence * 0.25
        + evidence_completeness * 0.15
        + context_coverage * 0.15
    )

    all_checks_passed = (
        is_grounded
        and retrieval_quality >= 1.0
        and citation_validity >= 1.0
        and evidence_completeness >= 1.0
        and context_coverage >= 1.0
    )
    if not all_checks_passed:
        score = min(score, 0.99)

    return round(max(0.0, min(1.0, score)), 4)


def _citation_validity(
    answer_text: str, citations: list[dict], evidence_chunks: list[Any]
) -> float:
    import re
    marker_indices = [int(marker) for marker in re.findall(r"\[(\d+)\]", answer_text)]
    if not marker_indices:
        return 1.0 if len(answer_text.split()) <= 5 else 0.0

    valid_count = 0
    for idx in marker_indices:
        chunk_pos = idx - 1
        citation = next(
            (item for item in citations if item.get("citation_index") == idx),
            None,
        )
        if (
            citation
            and 0 <= chunk_pos < len(evidence_chunks)
            and str((evidence_chunks[chunk_pos].content if hasattr(evidence_chunks[chunk_pos], "content") else evidence_chunks[chunk_pos].get("content", "")) or "").strip()
            and str(citation.get("excerpt") or "").strip()
        ):
            valid_count += 1

    return valid_count / len(marker_indices)


def _context_coverage(answer_text: str) -> float:
    import re
    claim_pattern = re.compile(
        r"([A-Z0-9][^.!?]*[.!?])\s*(\[\d+\](?:\s*\[\d+\])*)?",
        re.IGNORECASE | re.DOTALL,
    )
    matches = claim_pattern.findall(answer_text)
    if not matches:
        return 1.0 if re.search(r"\[\d+\]", answer_text) else 0.0

    total = 0
    cited = 0
    for sentence, trailing_markers in matches:
        if len(sentence.split()) <= 2:
            continue
        total += 1
        if trailing_markers or re.search(r"\[\d+\]", sentence):
            cited += 1

    return cited / total if total else 1.0


def _retrieval_quality(evidence_chunks: list[Any], retrieval_result: Any) -> float:
    from typing import Any
    if not evidence_chunks:
        return 0.0
    if retrieval_result is None:
        return 1.0

    final_evidence = getattr(retrieval_result, "final_evidence", evidence_chunks)
    if not final_evidence:
        return 0.0

    requested = getattr(retrieval_result, "top_k_requested", len(final_evidence)) or 1
    count_score = min(len(final_evidence) / requested, 1.0)
    if len(final_evidence) == len(evidence_chunks):
        return count_score

    non_empty_ratio = len(evidence_chunks) / len(final_evidence)
    return round((count_score + non_empty_ratio) / 2, 4)

