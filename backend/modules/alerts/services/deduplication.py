import uuid


class AlertDeduplicationEngine:
    def __init__(self):
        self._mock_redis = {}

    async def check_and_set_cooldown(
        self, rule_id: uuid.UUID, cooldown_minutes: int
    ) -> bool:
        key = f"raguard:alert:cooldown:{rule_id}"
        if key in self._mock_redis:
            return False
        self._mock_redis[key] = True
        return True
