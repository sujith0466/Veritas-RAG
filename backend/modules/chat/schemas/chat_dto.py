from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageDTO(BaseModel):
    id: str
    session_id: str
    role: str
    message: str
    citations: list[dict[str, Any]] | None = None
    reliability_score: float | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatSessionDTO(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    pinned: bool
    archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatSessionCreateDTO(BaseModel):
    title: str | None = Field(default="New Chat")

class ChatSessionUpdateDTO(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None

class ChatMessageCreateDTO(BaseModel):
    role: str
    message: str
    citations: list[dict[str, Any]] | None = None
    reliability_score: float | None = None
    metadata_json: dict[str, Any] | None = None

class ChatRequestDTO(BaseModel):
    query: str = Field(..., description="The user's chat message")
    stream: bool = Field(default=True, description="Whether to stream the response")
    max_answer_tokens: int = Field(default=1024)
    workspace_id: uuid.UUID | None = Field(default=None, description="Optional workspace identifier")
