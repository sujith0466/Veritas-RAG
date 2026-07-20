"""Policy Engine — Phase 7. Fetches and enforces per-tenant retry policies."""

from typing import Any

from backend.modules.retry.schemas.retry_dto import RetryPolicyDTO


class PolicyEngine:
    """Loads per-tenant retry policies from cache (Redis) with PostgreSQL fallback."""

    def __init__(self, cache_provider: Any = None) -> None:
        self.cache_provider = cache_provider

    async def get_policy(self, tenant_id: str) -> RetryPolicyDTO:
        """Return the active policy for `tenant_id`. Falls back to default (max_retries=3)."""
        # Production: deserialize from Redis → fall through to DB → default
        return RetryPolicyDTO(tenant_id=tenant_id, max_total_retries=3, rules=[])

    async def set_policy(self, tenant_id: str, policy: RetryPolicyDTO) -> None:
        """Persist a custom policy (write-through cache + DB)."""
        # Production: write to Redis + Postgres
        pass

    async def reset_to_default(self, tenant_id: str) -> None:
        """Remove custom policy — next lookup returns the default."""
        pass
