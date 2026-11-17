"""Pydantic schemas for workspace ownership transfer endpoints.
Governed by Section 7 Batch 1 & Batch 2 (V3.0).
"""

from datetime import datetime
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class OwnershipNominationCreate(BaseModel):
    """Payload to initiate an ownership nomination."""

    nominee_user_id: uuid.UUID = Field(
        ..., description="The user ID of the active ADMIN or MEMBER to nominate as OWNER"
    )


class OwnershipRejectionCreate(BaseModel):
    """Payload to reject an ownership nomination."""

    rejection_reason: Optional[str] = Field(
        None, max_length=500, description="Optional reason for declining the nomination (max 500 chars)"
    )


class FormerOwnerChoiceCreate(BaseModel):
    """Payload for former owner to select STAY or LEAVE."""

    choice: Literal["STAY", "LEAVE"] = Field(
        ..., description="Former owner disposition choice: STAY (remain in workspace) or LEAVE (depart immediately)"
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Optional notes accompanying choice"
    )


class RoleDecisionCreate(BaseModel):
    """Payload for new owner to decide former owner's role."""

    decision: Literal["ADMIN", "MEMBER", "REMOVE"] = Field(
        ..., description="Role decision for former owner: ADMIN, MEMBER, or REMOVE. VIEWER prohibited."
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Optional feedback or notes on the role decision"
    )


class OwnershipTransferUserDTO(BaseModel):
    """Minimal representation of a user involved in transfer."""

    id: uuid.UUID
    email: str
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OwnershipTransferResponse(BaseModel):
    """Response DTO for an ownership transfer record."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    nominated_by_user_id: uuid.UUID
    nominee_user_id: uuid.UUID
    status: str
    rejection_reason: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    responded_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    is_expired: bool = False

    # Batch 2 Lifecycle fields
    former_owner_choice: str = "PENDING"
    former_owner_choice_at: Optional[datetime] = None
    decision_status: str = "PENDING"
    decision_deadline_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by_user_id: Optional[uuid.UUID] = None
    response_notes: Optional[str] = None
    decision_notes: Optional[str] = None

    # Batch 3 Lifecycle & PII Snapshot fields (WP 7.12, WP 7.13)
    current_owner_email_snapshot: Optional[str] = None
    nominated_user_email_snapshot: Optional[str] = None

    nominated_by: Optional[OwnershipTransferUserDTO] = None
    nominee: Optional[OwnershipTransferUserDTO] = None

    model_config = ConfigDict(from_attributes=True)
