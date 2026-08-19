import socket
import pytest
from backend.cache.client import get_redis_client


def _is_redis_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=0.05):
            return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
async def reset_rate_limits():
    """Ensure deterministic rate-limit state across tests without modifying production limits."""
    if not _is_redis_open():
        yield
        return

    redis = get_redis_client()
    if redis:
        try:
            await redis.flushdb()
        except Exception:
            pass
    yield
