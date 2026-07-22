from backend.modules.analytics.schemas.errors import QuotaExceededError


class QuotaGovernor:
    def __init__(self):
        self._mock_redis = {}
        # Pre-seed some mock quota limits
        self._mock_redis["quota:tokens:t1"] = 100000

    async def check_and_reserve(self, tenant_id: str, est_tokens: int) -> bool:
        key = f"quota:tokens:{tenant_id}"
        current = self._mock_redis.get(key, 0)

        if current < est_tokens:
            raise QuotaExceededError(f"Quota exhausted for tenant {tenant_id}")

        self._mock_redis[key] = current - est_tokens
        return True

    async def adjust_reservation_diff(self, tenant_id: str, diff_tokens: int):
        # Refund unused tokens, or subtract if underestimated
        key = f"quota:tokens:{tenant_id}"
        current = self._mock_redis.get(key, 0)
        self._mock_redis[key] = current + diff_tokens
