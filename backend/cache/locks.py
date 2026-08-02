"""Distributed Locking Foundation.

Provides safe mutexes for background task synchronization across workers.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import uuid

from backend.cache.client import get_redis_client
from backend.core.exceptions.infrastructure import InfrastructureException


class LockAcquisitionError(InfrastructureException):
    """Raised when a distributed lock cannot be acquired."""
    pass


@asynccontextmanager
async def acquire_lock(
    lock_name: str,
    timeout: int = 60,
    acquire_timeout: int = 5,
    retry_delay: float = 0.5
) -> AsyncGenerator[str, None]:
    """Acquire a distributed Redis lock safely.

    Uses an async context manager to guarantee the lock is released when
    the block exits or if an exception is raised.

    Args:
        lock_name: The unique name for the lock.
        timeout: How long (in seconds) the lock is held before auto-releasing.
        acquire_timeout: How long to wait trying to acquire the lock.
        retry_delay: Delay between acquisition attempts.

    Yields:
        The lock token if successful.

    Raises:
        LockAcquisitionError: If the lock cannot be acquired within the timeout.
    """
    client = get_redis_client()
    lock_token = str(uuid.uuid4())
    lock_key = f"lock:{lock_name}"

    acquired = False
    deadline = asyncio.get_running_loop().time() + acquire_timeout

    try:
        while asyncio.get_running_loop().time() < deadline:
            # SET NX EX
            # NX: Set only if it does not exist
            # EX: Expiry in seconds
            acquired = await client.set(lock_key, lock_token, nx=True, ex=timeout)
            if acquired:
                break
            await asyncio.sleep(retry_delay)

        if not acquired:
            raise LockAcquisitionError(f"Failed to acquire lock '{lock_name}' within {acquire_timeout}s.")

        yield lock_token

    finally:
        if acquired:
            # Lua script to ensure we only delete the lock if we still own it (token matches)
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await client.eval(script, 1, lock_key, lock_token)
