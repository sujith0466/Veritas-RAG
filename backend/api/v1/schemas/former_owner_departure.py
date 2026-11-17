"""Pydantic schemas for former owner departure history and user deletion eligibility.

Governed by Section 7 Batch 3 (WP 7.9, WP 7.10, PO-D32-03).
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FormerOwnerDepartureUserDTO(BaseModel):
    """Minimal representation of a user in departure records."""

    id: uuid.UUID
    email: Optional[str] = None
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FormerOwnerDepartureResponse(BaseModel):
    """Response DTO for an immutable workspace former owner departure record."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    former_owner_id: uuid.UUID
    transfer_id: uuid.UUID
    departure_type: str = Field(
        ...,
        description="Outcome: VOLUNTARY_LEAVE, NEW_OWNER_REMOVED, NEW_OWNER_RETAINED, TIMEOUT_AUTO_REMOVED",
    )
    former_role: str = "OWNER"
    retained_role: Optional[str] = None
    departure_confirmed_at: datetime
    confirmed_by_user_id: uuid.UUID
    departure_notes: Optional[str] = None
    created_at: datetime

    former_owner: Optional[FormerOwnerDepartureUserDTO] = None
    confirmed_by: Optional[FormerOwnerDepartureUserDTO] = None

    model_config = ConfigDict(from_attributes=True)


class UserDeletionEligibilityResponse(BaseModel):
    """Response DTO for user deletion / deactivation eligibility evaluation (WP 7.9)."""

    eligible: bool
    rejection_code: Optional[str] = None
    rejection_reason: Optional[str] = None
    details: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
