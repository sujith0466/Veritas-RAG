"""Clarification State Manager — Phase 9.

Manages active clarification requests with expiration, state transitions,
and persistence across paused query executions.
"""

import time

from structlog import get_logger

from backend.modules.query_rewrite.schemas.errors import ClarificationGenerationFailed
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    ClarificationResumeRequestDTO,
    ClarificationStateDTO,
    ClarificationStatus,
    ClarifiedQueryDTO,
)

logger = get_logger(__name__)


class ClarificationStateManager:
    """Thread-safe memory/cache store for pending clarification requests."""

    def __init__(self, default_ttl_seconds: int = 600) -> None:
        self.default_ttl = default_ttl_seconds
        self._store: dict[str, ClarificationStateDTO] = {}

    def save_state(
        self,
        correlation_id: str,
        tenant_id: str,
        original_query: str,
        question_text: str,
        options: list[str],
    ) -> ClarificationStateDTO:
        """Create and store a new required clarification state."""
        now = time.time()
        state = ClarificationStateDTO(
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            original_query=original_query,
            question_text=question_text,
            options=options,
            status=ClarificationStatus.REQUIRED,
            created_at=now,
            expires_at=now + self.default_ttl,
        )
        self._store[correlation_id] = state
        logger.info(
            "Saved clarification state",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
        return state

    def get_state(self, correlation_id: str) -> ClarificationStateDTO | None:
        """Retrieve state, checking for expiration."""
        state = self._store.get(correlation_id)
        if not state:
            return None
        if (
            time.time() > state.expires_at
            and state.status == ClarificationStatus.REQUIRED
        ):
            state.status = ClarificationStatus.TIMEOUT
            logger.warning("Clarification state expired", correlation_id=correlation_id)
        return state

    def resolve_state(
        self,
        resume_req: ClarificationResumeRequestDTO,
    ) -> ClarifiedQueryDTO:
        """Resolve clarification state using user selection."""
        state = self.get_state(resume_req.correlation_id)
        if not state:
            raise ClarificationGenerationFailed(
                f"No pending clarification state found for correlation_id: {resume_req.correlation_id}"
            )
        if state.status == ClarificationStatus.TIMEOUT:
            raise ClarificationGenerationFailed(
                f"Clarification request {resume_req.correlation_id} has timed out."
            )
        if state.status != ClarificationStatus.REQUIRED:
            raise ClarificationGenerationFailed(
                f"Clarification request {resume_req.correlation_id} is already in state: {state.status}"
            )

        # Merge selected option and additional context
        selected = resume_req.selected_option.strip()
        context_suffix = (
            f" (Context: {resume_req.additional_context.strip()})"
            if resume_req.additional_context
            else ""
        )
        clarified_query = f"{state.original_query} — specifically focusing on: {selected}{context_suffix}"

        state.status = ClarificationStatus.RESOLVED
        state.selected_option = selected
        state.clarified_query = clarified_query

        logger.info(
            "Clarification resolved successfully",
            correlation_id=state.correlation_id,
            clarified_query=clarified_query,
        )
        return ClarifiedQueryDTO(
            correlation_id=state.correlation_id,
            original_query=state.original_query,
            clarified_query=clarified_query,
            resolution_summary=f"Resolved with option '{selected}'{context_suffix}",
        )

    def cleanup_expired(self) -> int:
        """Purge expired states."""
        now = time.time()
        expired_ids = [cid for cid, st in self._store.items() if now > st.expires_at]
        for cid in expired_ids:
            self._store.pop(cid, None)
        return len(expired_ids)
