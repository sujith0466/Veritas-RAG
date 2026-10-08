import pytest
import redis
from backend.core.config import get_settings


def _get_sync_redis() -> redis.Redis | None:
    try:
        settings = get_settings()
        url = settings.redis.test_url if settings.is_testing else settings.redis.url
        r = redis.Redis.from_url(url, socket_timeout=0.2)
        if r.ping():
            return r
    except Exception:
        pass
    return None


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Ensure deterministic rate-limit state across tests without modifying production limits."""
    r = _get_sync_redis()
    if r is not None:
        try:
            r.flushdb()
        except Exception:
            pass
    yield
    if r is not None:
        try:
            r.flushdb()
        except Exception:
            pass
