from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.database import get_db
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.retrieval.api.dependencies import get_retrieval_orchestrator
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService

async def get_chat_repository(session: AsyncSession = Depends(get_db)) -> ChatRepository:
    return ChatRepository(session)

async def get_chat_orchestrator(
    chat_repo: ChatRepository = Depends(get_chat_repository),
    retrieval_orchestrator = Depends(get_retrieval_orchestrator)
) -> ChatOrchestrator:
    from backend.ai.manager import LLMProviderManager
    from backend.ai.interfaces.llm_provider import LLMRequest
    from backend.modules.generation.services.citation_extractor import CitationExtractor
    from backend.modules.generation.services.prompt_guard import PromptGuard
    
    citation_extractor = CitationExtractor()
    prompt_guard = PromptGuard()
    
    class LLMAdapter:
        def __init__(self, provider):
            self.provider = provider
        async def generate_stream(self, query: str, evidence: str):
            prompt = f"Answer the following query using ONLY the provided evidence.\nYou MUST cite your sources by adding inline citations like [1], [2] at the end of each sentence based on the evidence chunk IDs.\n\nEvidence:\n{evidence}\n\nQuery:\n{query}"
            req = LLMRequest(prompt=prompt, system_instruction="You are a helpful assistant. You must cite evidence using [1], [2] format.")
            async for chunk in self.provider.stream(req):
                yield chunk
                
    real_llm_provider = LLMProviderManager()
    
    streaming_service = StreamingGroundedGenerationService(
        citation_extractor=citation_extractor,
        prompt_guard=prompt_guard,
        llm_provider=LLMAdapter(real_llm_provider)
    )
    
    return ChatOrchestrator(
        chat_repo=chat_repo,
        retrieval_orchestrator=retrieval_orchestrator,
        streaming_generation=streaming_service
    )
