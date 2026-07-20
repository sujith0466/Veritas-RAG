"""Generation REST API Routes — Phase 10."""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTO,
    GenerationRequestDTOv2,
    GroundedAnswerDTO,
)
from backend.modules.generation.services.generation_service import GroundedGenerationService
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService

router = APIRouter()
_extractor = CitationExtractor()
_prompt_guard = PromptGuard()
_service = GroundedGenerationService(citation_extractor=_extractor, llm_provider=None)
_streaming_service = StreamingGroundedGenerationService(citation_extractor=_extractor, prompt_guard=_prompt_guard)


@router.post("/generate/grounded", response_model=GroundedAnswerDTO, summary="Generate grounded answer with citations")
async def generate_grounded(request: GenerationRequestDTO) -> GroundedAnswerDTO:
    """Execute synchronous grounded answer generation ensuring every sentence is cited."""
    return _service.generate(request)


@router.post("/generate/stream", summary="Stream grounded answer via SSE")
async def generate_stream(request: GenerationRequestDTOv2):
    """Stream grounded answer chunks and live citations using Server-Sent Events (`SSE`)."""
    async def sse_generator():
        async for chunk in _streaming_service.generate_stream(request):
            payload = chunk.model_dump_json()
            yield f"data: {payload}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
