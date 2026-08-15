from backend.cache.client import get_redis_client
from backend.modules.analytics.schemas.errors import QuotaExceededError

class QuotaGovernor:
    """Manages workspace token quotas using Redis-backed token buckets."""
    
    async def get_remaining_tokens(self, tenant_id: str) -> int:
        """Fetch the current remaining tokens for the tenant."""
        redis = get_redis_client()
        key = f"quota:tokens:{tenant_id}"
        current = await redis.get(key)
        
        # If no quota is set in Redis, we default to 0 to trigger an update/fetch from DB
        # But for robust default fallback, F12.5 will initialize these buckets.
        return int(current) if current is not None else 0

    async def set_remaining_tokens(self, tenant_id: str, tokens: int) -> None:
        """Set the absolute remaining token limit."""
        redis = get_redis_client()
        key = f"quota:tokens:{tenant_id}"
        await redis.set(key, tokens)

    async def check_and_reserve(self, tenant_id: str, est_tokens: int) -> bool:
        """Atomically check if quota exists and subtract estimated tokens."""
        redis = get_redis_client()
        key = f"quota:tokens:{tenant_id}"
        
        # We use a simple Lua script to ensure atomicity
        lua_script = """
        local current = redis.call('get', KEYS[1])
        if current == false then
            return -1
        end
        local current_num = tonumber(current)
        local est = tonumber(ARGV[1])
        if current_num < est then
            return 0
        end
        redis.call('decrby', KEYS[1], est)
        return 1
        """
        result = await redis.eval(lua_script, 1, key, est_tokens)
        
        if result == -1:
            # Uninitialized bucket, fallback to DB logic (temporarily we can assume exhausted until initialized)
            raise QuotaExceededError(f"Quota uninitialized for tenant {tenant_id}")
        elif result == 0:
            raise QuotaExceededError(f"Quota exhausted for tenant {tenant_id}")
            
        return True

    async def adjust_reservation_diff(self, tenant_id: str, diff_tokens: int):
        """Refund unused tokens, or subtract if underestimated."""
        redis = get_redis_client()
        key = f"quota:tokens:{tenant_id}"
        # diff_tokens is positive to add (refund), negative to subtract
        await redis.incrby(key, diff_tokens)
