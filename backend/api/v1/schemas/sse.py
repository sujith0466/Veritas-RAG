from typing import Literal

from pydantic import BaseModel, ConfigDict

# Reserved SSE event types
SSEEventType = Literal[
    "connected",
    "heartbeat",
    "progress",
    "retrieval",
    "reasoning",
    "metadata",
    "citations",
    "reliability",
    "citation",
    "reliability_score",
    "warning",
    "error",
    "done",
    "chunk", # Standard text chunk
]

class SSEErrorPayload(BaseModel):
    """Structured Error payload for SSE events."""
    code: str
    message: str
    retry_after: int | None = None
    correlation_id: str | None = None
    recoverable: bool = False

class SSEMessageDTO(BaseModel):
    """
    Standard DTO for Server-Sent Events serialization.
    Implements F8.3 standard and F8.4 structured payload requirements.
    """
    id: str | None = None
    event: SSEEventType | str | None = "chunk"
    data: str | None = None
    retry: int | None = None
    comment: str | None = None

    model_config = ConfigDict(extra="forbid")

    def to_sse_string(self) -> str:
        """Serialize to standard SSE string format."""
        parts = []
        if self.comment:
            parts.append(f": {self.comment}")
        if self.id is not None:
            parts.append(f"id: {self.id}")
        if self.event is not None:
            parts.append(f"event: {self.event}")
        if self.data is not None:
            for line in self.data.split("\n"):
                parts.append(f"data: {line}")
        if self.retry is not None:
            parts.append(f"retry: {self.retry}")

        if not parts:
            return "\n\n"
        return "\n".join(parts) + "\n\n"

    @classmethod
    def heartbeat(cls) -> "SSEMessageDTO":
        return cls(event="heartbeat", data="{}", comment="keepalive")

    @classmethod
    def error(cls, code: str, message: str, correlation_id: str | None = None, retry_after: int | None = None, recoverable: bool = False) -> "SSEMessageDTO":
        payload = SSEErrorPayload(
            code=code,
            message=message,
            correlation_id=correlation_id,
            retry_after=retry_after,
            recoverable=recoverable
        )
        return cls(event="error", data=payload.model_dump_json())

    @classmethod
    def format_id(cls, correlation_id: str, chunk_index: int) -> str:
        """Use safe delimiter (:) for Last-Event-ID."""
        return f"{correlation_id}:{chunk_index}"
