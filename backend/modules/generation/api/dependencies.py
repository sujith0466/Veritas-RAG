from fastapi import Depends

from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)

def get_citation_extractor() -> CitationExtractor:
    return CitationExtractor()

def get_prompt_guard() -> PromptGuard:
    return PromptGuard()

def get_streaming_generation_service(
    citation_extractor: CitationExtractor = Depends(get_citation_extractor),
    prompt_guard: PromptGuard = Depends(get_prompt_guard),
) -> StreamingGroundedGenerationService:
    return StreamingGroundedGenerationService(
        citation_extractor=citation_extractor,
        prompt_guard=prompt_guard,
    )
