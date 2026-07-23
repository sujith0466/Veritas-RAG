from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_async_session
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.retrieval.api.dependencies import get_retrieval_orchestrator
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService

async def get_chat_repository(session: AsyncSession = Depends(get_async_session)) -> ChatRepository:
    return ChatRepository(session)

async def get_chat_orchestrator(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    retrieval_orchestrator = Depends(get_retrieval_orchestrator)
) -> ChatOrchestrator:
    # Need to instantiate the StreamingGroundedGenerationService
    citation_extractor = CitationExtractor()
    prompt_guard = PromptGuard()
    
    streaming_service = StreamingGroundedGenerationService(
        citation_extractor=citation_extractor,
        prompt_guard=prompt_guard,
        llm_provider=None # Uses deterministic mock fallback as per existing codebase
    )
    
    return ChatOrchestrator(
        chat_repo=chat_repo,
        retrieval_orchestrator=retrieval_orchestrator,
        streaming_generation=streaming_service
    )
