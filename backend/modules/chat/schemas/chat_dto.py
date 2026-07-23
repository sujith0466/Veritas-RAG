from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

class ChatMessageDTO(BaseModel):
    id: str
    session_id: str
    role: str
    message: str
    citations: Optional[List[Dict[str, Any]]] = None
    reliability_score: Optional[float] = None
    metadata_json: Optional[Dict[str, Any]] = None
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
    messages: Optional[List[ChatMessageDTO]] = []
    
    model_config = ConfigDict(from_attributes=True)

class ChatSessionCreateDTO(BaseModel):
    title: Optional[str] = Field(default="New Chat")

class ChatSessionUpdateDTO(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None

class ChatMessageCreateDTO(BaseModel):
    role: str
    message: str
    citations: Optional[List[Dict[str, Any]]] = None
    reliability_score: Optional[float] = None
    metadata_json: Optional[Dict[str, Any]] = None

class ChatRequestDTO(BaseModel):
    query: str = Field(..., description="The user's chat message")
    stream: bool = Field(default=True, description="Whether to stream the response")
    max_answer_tokens: int = Field(default=1024)
