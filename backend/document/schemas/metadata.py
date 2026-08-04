"""Metadata Schemas."""

from typing import Any

from pydantic import BaseModel, Field


class MetadataUpdatePayload(BaseModel):
    """Payload for full metadata overwrite or partial patch."""

    metadata: dict[str, Any] = Field(
        ...,
        description="Key-value dictionary. Max 100 keys. Values can be strings, numbers, or booleans.",
    )
