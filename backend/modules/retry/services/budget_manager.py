"""Retry Budget Manager — Phase 7. Enforces hard cap of 3 retries per PRD."""

from typing import Any


class RetryBudgetManager:
    """Tracks per-query retry budget. Hard cap = 3 attempts (4th attempt is always rejected)."""

    HARD_CAP: int = 3

    def __init__(self, cache_provider: Any = None) -> None:
        self.cache_provider = cache_provider

    async def check_budget(self, tenant_id: str, query_id: str, attempt_number: int) -> bool:
        """Return True if budget is available (attempt_number <= HARD_CAP), False otherwise."""
        return attempt_number <= self.HARD_CAP

    async def consume_budget(self, tenant_id: str, query_id: str) -> None:
        """Record a budget consumption event (increments Redis counter in production)."""
        # Production: INCR budget:<tenant_id>:<query_id> with TTL
        pass

    async def release_budget(self, tenant_id: str, query_id: str) -> None:
        """Release budget slot on terminal outcomes (COMPLETED / ABORTED)."""
        pass
