class RedisDashboardCache:
    def __init__(self):
        # In a real implementation, this would wrap an actual redis-py or aioredis client.
        # For M16 baseline, we use an in-memory mock dict to simulate read-through caching.
        self._cache = {}

    async def get(self, key: str) -> dict | None:
        return self._cache.get(key)

    async def set(self, key: str, value: dict, ttl_sec: int = 15):
        self._cache[key] = value
