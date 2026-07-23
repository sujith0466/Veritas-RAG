import asyncio
from collections.abc import AsyncGenerator
from typing import Any, List, Dict
import json
import uuid
from structlog import get_logger

from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.schemas import ChatMessageCreateDTO
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.generation.schemas.generation_dto import GenerationRequestDTOv2, StreamingGenerationChunkDTO
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService

logger = get_logger(__name__)

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
        
        # 1. Save User Message
        await self.chat_repo.add_message(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            dto=ChatMessageCreateDTO(
                role="user",
                message=query
            )
        )

        # 2. Retrieve Evidence (Hybrid Search)
        search_request = SearchRequestDTO(
            query=query,
            top_k=5,
            rerank=True,
            semantic_weight=0.7
        )
        
        try:
            retrieval_result = await self.retrieval_orchestrator.execute_hybrid_search(
                options=search_request,
                tenant_id=tenant_id,
                correlation_id=correlation_id
            )
            
            # Map retrieval results to generation evidence format
            evidence_chunks = [
                {
                    "id": c.chunk_id,
                    "content": c.content,
                    "document_id": c.document_id,
                    "relevance_score": c.score
                }
                for c in retrieval_result.top_candidates
            ]
        except Exception as e:
            logger.error("Chat retrieval failed", error=str(e))
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
        
        async for chunk in self.streaming_generation.generate_stream(gen_request):
            if chunk.text_delta:
                full_assistant_text += chunk.text_delta
            if chunk.is_final:
                final_citations = [c.model_dump() for c in chunk.citations_delta]
                is_grounded = chunk.is_fully_grounded
                
            yield f"data: {chunk.model_dump_json()}\n\n"
            
        # 4. Save Assistant Message
        await self.chat_repo.add_message(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            dto=ChatMessageCreateDTO(
                role="assistant",
                message=full_assistant_text.strip(),
                citations=final_citations,
                reliability_score=1.0 if is_grounded else 0.5,
                metadata_json={"is_fully_grounded": is_grounded}
            )
        )
