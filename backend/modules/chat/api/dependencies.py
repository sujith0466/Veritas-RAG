from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.database import get_db
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.retrieval.api.dependencies import get_retrieval_orchestrator


async def get_chat_repository(session: AsyncSession = Depends(get_db)) -> ChatRepository:
    return ChatRepository(session)

from backend.ai.api.dependencies import get_ai_wrapper_service
from backend.ai.wrapper.service import AIWrapperService

async def get_chat_orchestrator(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    ai_wrapper_service: AIWrapperService = Depends(get_ai_wrapper_service)
) -> ChatOrchestrator:
    return ChatOrchestrator(
        chat_repo=chat_repo,
        ai_wrapper_service=ai_wrapper_service
    )
