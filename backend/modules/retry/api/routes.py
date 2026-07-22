"""Retry Controller REST API — Phase 7."""

from fastapi import APIRouter

from backend.modules.retry.schemas.retry_dto import (RetryDecisionDTO,
                                                     RetryRequestContextDTO)
from backend.modules.retry.services.retry_controller import RetryController

router = APIRouter()
_controller = RetryController()


@router.post(
    "/decide", response_model=RetryDecisionDTO, summary="Evaluate retry decision"
)
async def decide_retry(context: RetryRequestContextDTO) -> RetryDecisionDTO:
    """Given a RetryRequestContextDTO, return the appropriate RetryDecisionDTO.

    Enforces:
    - Hard cap of 3 retries (PRD requirement)
    - Monotonic improvement check
    - Per-tenant policy evaluation
    - Exponential backoff calculation
    """
    return await _controller.handle_retry(context)


@router.delete("/history/{query_id}", summary="Clear retry history for a query")
async def clear_retry_history(query_id: str) -> dict[str, str]:
    """Clear in-process score history for a terminated query_id."""
    _controller.clear_history(query_id)
    return {"status": "cleared", "query_id": query_id}
