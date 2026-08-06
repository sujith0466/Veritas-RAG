from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO


class NamespaceBinding(BaseModel):
    """Result of namespace resolution for Qdrant collection."""
    workspace_id: UUID
    tenant_id: UUID
    collection_name: str


class AIWrapperRequest(BaseModel):
    """The canonical input to the AI platform orchestration layer."""
    model_config = ConfigDict(extra="forbid")

    session_id: UUID | None = None
    workspace_id: UUID
    tenant_id: UUID
    query: str
    conversation_history: list[dict[str, Any]] = []
    guardrail_config: dict[str, Any] = {}
    stream: bool = True
    max_answer_tokens: int = 1024


class AIWrapperResponse(BaseModel):
    """Non-streaming response from the AI wrapper."""
    content: str
    is_fully_grounded: bool
    reliability_score: float
    citations: list[dict[str, Any]]
    metadata: dict[str, Any] = {}


class AIWrapperStreamChunk(StreamingGenerationChunkDTO):
    """Extends existing chunk DTO with wrapper-specific metadata."""
    namespace_used: str | None = None
    wrapper_metadata: dict[str, Any] | None = None


class V1EngineStreamChunk(BaseModel):
    """Represents an SSE chunk directly from the V1 Engine."""
    text_delta: str = ""
    is_final: bool = False
    chunk_index: int = 0
    model_used: str | None = None
    type: str | None = None
