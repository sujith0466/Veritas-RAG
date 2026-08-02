import asyncio
from collections.abc import AsyncGenerator
from typing import Any, List, Dict
import json
import re
import uuid
import time
from structlog import get_logger

from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.schemas import ChatMessageCreateDTO
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.generation.schemas.generation_dto import GenerationRequestDTOv2, StreamingGenerationChunkDTO
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService

logger = get_logger(__name__)


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


class ChatOrchestrator:
    """Orchestrates RAG chat flows: retrieval -> streaming generation -> persistence."""

    def __init__(
        self,
        chat_repo: ChatRepository,
        retrieval_orchestrator: RetrievalOrchestrator,
        streaming_generation: StreamingGroundedGenerationService
    ):
        self.chat_repo = chat_repo
        self.retrieval_orchestrator = retrieval_orchestrator
        self.streaming_generation = streaming_generation

    async def stream_chat(
        self, 
        session_id: str, 
        tenant_id: str, 
        user_id: str, 
        query: str,
        correlation_id: str
    ) -> AsyncGenerator[str, None]:
        from backend.database.engine import get_session_factory
        session_maker = get_session_factory()
        started_at = time.perf_counter()
        
        # 1. Save User Message
        async with session_maker() as session:
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
        
        # 1.5 Check if knowledge base is still processing
        from backend.document.models.document import Document
        from backend.document.models.status import DocumentStatus
        from sqlalchemy import select
        
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
            # Check for any READY documents
            ready_result = await session.execute(
                select(Document).where(
                    Document.tenant_id == tenant_id,
                    Document.status == DocumentStatus.READY
                ).limit(1)
            )
            has_ready_doc = ready_result.scalar_one_or_none() is not None
            
            # If no READY documents exist, check if we are still processing others
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
                
                # Stream the message
                chunk = StreamingGenerationChunkDTO(
                    chunk_index=0,
                    text_delta=msg,
                    is_final=True,
                    is_fully_grounded=True,
                    citations_delta=[],
                    correlation_id=correlation_id
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
                
                # Save assistant message
                async with session_maker() as session:
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
                return




        # 2. Retrieve Evidence (Hybrid Search)
        search_request = SearchRequestDTO(
            query=query,
            top_k=5,
            rerank=True,
            semantic_weight=0.7
        )
        
        retrieval_result = None
        try:
            retrieval_result = await self.retrieval_orchestrator.execute_hybrid_search(
                options=search_request,
                tenant_id=tenant_id,
                correlation_id=correlation_id
            )
            
            # Use the canonical DTOs directly to preserve metadata
            evidence_chunks = retrieval_result.final_evidence if retrieval_result.final_evidence else []


        except Exception as e:
            logger.error("Chat retrieval failed", error=str(e))
            import traceback
            traceback.print_exc()
            evidence_chunks = []

        # 3. Stream Generation & Build Final Message
        gen_request = GenerationRequestDTOv2(
            query=query,
            evidence_chunks=evidence_chunks,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            stream=True
        )
        
        full_assistant_text = ""
        final_citations = []
        is_grounded = False
        

        
        try:
            chunk_count = 0
            async for chunk in self.streaming_generation.generate_stream(gen_request):
                chunk_count += 1
                if chunk.text_delta:
                    full_assistant_text += chunk.text_delta

                if chunk.is_final:
                    final_citations = [c.model_dump() for c in chunk.citations_delta]
                    is_grounded = chunk.is_fully_grounded
                    
                yield f"data: {chunk.model_dump_json()}\n\n"


        except Exception as e:

            raise


        reliability_score = compute_chat_reliability_score(
            answer_text=full_assistant_text,
            evidence_chunks=evidence_chunks,
            citations=final_citations,
            is_grounded=bool(is_grounded),
            retrieval_result=retrieval_result,
        )
            
        # 4. Save Assistant Message
        async with session_maker() as session:
            repo = ChatRepository(session)
            await repo.add_message(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                dto=ChatMessageCreateDTO(
                    role="assistant",
                    message=full_assistant_text.strip(),
                    citations=final_citations,
                    reliability_score=reliability_score,
                    metadata_json={
                        "is_fully_grounded": is_grounded,
                        "reliability_score": reliability_score,
                    }
                )
            )


        duration_seconds = time.perf_counter() - started_at
        outcome = "SUCCESS" if is_grounded else "UNGROUNDED"

        try:
            from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
            from backend.observability.metrics import (
                record_query_metric,
                record_reliability_metric,
            )

            async with session_maker() as session:
                session.add(
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
                await session.commit()

            record_query_metric(tenant_id, outcome, duration_seconds)
            record_reliability_metric(reliability_score)
        except Exception as exc:
            logger.error(
                "Chat analytics recording failed",
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
