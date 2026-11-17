"""Schemas for Platform Admin Ownerless Workspace Recovery (DEC-01)."""

import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OwnerRecoveryRequest(BaseModel):
    """Payload for platform-admin owner recovery."""

    model_config = ConfigDict(extra="forbid")

    target_user_id: uuid.UUID = Field(
        ...,
        description="UUID of the active, verified workspace member to promote to OWNER.",
    )
    justification_ticket_id: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Mandatory issue or change-management ticket ID (e.g. SEC-1234, INC-5678).",
    )
    justification_reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Detailed operational justification for the break-glass recovery action.",
    )

    @field_validator("justification_ticket_id")
    @classmethod
    def validate_ticket_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("justification_ticket_id must not be empty or whitespace only.")
        return s

    @field_validator("justification_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        s = v.strip()
        if not s or len(s) < 10:
            raise ValueError("justification_reason must contain at least 10 non-whitespace characters.")
        return s


class OwnerRecoveryResponse(BaseModel):
    """Response payload returned upon successful owner recovery."""

    workspace_id: uuid.UUID
    promoted_user_id: uuid.UUID
    previous_role: str
    new_role: str = "OWNER"
    justification_ticket_id: str
    recovered_at: str
    recovery_status: str = "COMPLETED"
