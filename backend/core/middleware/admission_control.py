"""Crash-Safe Admission Control Middleware (`WP-3C Phase 2`, `TSK-3C-05`, `ADR-005`).

Enforces fail-closed admission barriers for mutating HTTP requests during maintenance
and backup quiescence windows using Redis per-writer leases and Lua scripts.
Also provides PostgreSQL transaction advisory lock helpers for database writer fencing.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import os
import time
from typing import Any
import uuid

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.cache.client import get_redis_client

logger = structlog.get_logger(__name__)

# Redis Key Constants
MAINTENANCE_MODE_KEY = "system:maintenance:mode"
RECOVERY_LOCKED_KEY = "system:maintenance:recovery_locked"
WRITER_KEY_PREFIX = "system:maintenance:writer:"
WRITERS_SET_KEY = "system:maintenance:writers_set"

DEFAULT_WRITER_TTL_SECONDS = 30
HEARTBEAT_INTERVAL_SECONDS = 10

# Lua Scripts
ADMIT_MUTATION_SCRIPT = """
local mode = redis.call("get", KEYS[1])
if mode and mode ~= "" then
    return -1
end
local locked = redis.call("get", KEYS[2])
if locked and locked ~= "" then
    return -2
end
redis.call("set", KEYS[3], ARGV[1], "EX", ARGV[2])
redis.call("sadd", KEYS[4], ARGV[1])
return 1
"""

RENEW_MUTATION_SCRIPT = """
local val = redis.call("get", KEYS[1])
if val == ARGV[1] then
    redis.call("expire", KEYS[1], ARGV[2])
    return 1
else
    return 0
end
"""

RELEASE_MUTATION_SCRIPT = """
local val = redis.call("get", KEYS[1])
if val == ARGV[1] then
    redis.call("del", KEYS[1])
    redis.call("srem", KEYS[2], ARGV[1])
    return 1
else
    return 0
end
"""

CHECK_ACTIVE_WRITERS_SCRIPT = """
local writers = redis.call("smembers", KEYS[1])
local active_count = 0
for _, token in ipairs(writers) do
    if redis.call("exists", ARGV[1] .. token) == 1 then
        active_count = active_count + 1
    else
        redis.call("srem", KEYS[1], token)
    end
end
return active_count
"""


async def acquire_snapshot_barrier_shared(session: AsyncSession) -> bool:
    """Acquire PostgreSQL shared transaction advisory lock before executing mutations.

    Incompatible with coordinator's exclusive advisory lock. Returns True if acquired,
    False if coordinator holds exclusive barrier (fails closed).
    """
    try:
        res = await session.execute(
            text("SELECT pg_try_advisory_xact_lock_shared(hashtext('veritas:snapshot:barrier'))")
        )
        return bool(res.scalar())
    except Exception as exc:
        logger.error("Failed to acquire shared advisory lock", error=str(exc))
        return False


async def acquire_snapshot_barrier_exclusive(session: AsyncSession) -> bool:
    """Acquire coordinator's PostgreSQL exclusive session advisory lock for snapshot isolation."""
    try:
        res = await session.execute(
            text("SELECT pg_try_advisory_lock(hashtext('veritas:snapshot:barrier'))")
        )
        return bool(res.scalar())
    except Exception as exc:
        logger.error("Failed to acquire exclusive advisory lock", error=str(exc))
        return False


async def release_snapshot_barrier_exclusive(session: AsyncSession) -> bool:
    """Release coordinator's PostgreSQL exclusive session advisory lock."""
    try:
        res = await session.execute(
            text("SELECT pg_advisory_unlock(hashtext('veritas:snapshot:barrier'))")
        )
        return bool(res.scalar())
    except Exception as exc:
        logger.error("Failed to release exclusive advisory lock", error=str(exc))
        return False


class AdmissionControlMiddleware(BaseHTTPMiddleware):
    """Enforces fail-closed admission control for mutating HTTP requests during quiescence."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    EXCLUDED_PREFIXES = (
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    )

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Redis[Any] | None = None,
        writer_ttl_seconds: int = DEFAULT_WRITER_TTL_SECONDS,
        heartbeat_interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(app)
        self._redis = redis_client
        self.writer_ttl_seconds = writer_ttl_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    @property
    def redis(self) -> Redis[Any]:
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def _is_mutating_request(self, request: Request) -> bool:
        if request.method not in self.MUTATING_METHODS:
            return False
        path = request.url.path
        for prefix in self.EXCLUDED_PREFIXES:
            if path.startswith(prefix):
                return False
        return True

    def _generate_writer_token(self) -> str:
        return f"{os.getpid()}:{uuid.uuid4()}"

    async def _admit_writer(self, token: str) -> int:
        """Call Lua script to atomically check maintenance status and register writer lease.

        Returns:
            1: Admitted cleanly.
            -1: Maintenance mode active.
            -2: Recovery locked.
        """
        try:
            res = await self.redis.eval(
                ADMIT_MUTATION_SCRIPT,
                4,
                MAINTENANCE_MODE_KEY,
                RECOVERY_LOCKED_KEY,
                f"{WRITER_KEY_PREFIX}{token}",
                WRITERS_SET_KEY,
                token,
                str(self.writer_ttl_seconds),
            )
            return int(res)
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.error("Redis error during mutation admission; failing closed", error=str(exc))
            return -1

    async def _renew_writer(self, token: str) -> bool:
        try:
            res = await self.redis.eval(
                RENEW_MUTATION_SCRIPT,
                1,
                f"{WRITER_KEY_PREFIX}{token}",
                token,
                str(self.writer_ttl_seconds),
            )
            return bool(int(res) == 1)
        except Exception:
            return False

    async def _release_writer(self, token: str) -> bool:
        try:
            res = await self.redis.eval(
                RELEASE_MUTATION_SCRIPT,
                2,
                f"{WRITER_KEY_PREFIX}{token}",
                WRITERS_SET_KEY,
                token,
            )
            return bool(int(res) == 1)
        except Exception as exc:
            logger.warning("Failed to release writer lease", token=token, error=str(exc))
            return False

    async def _heartbeat_loop(self, token: str, stop_event: asyncio.Event) -> None:
        """Periodically renew writer lease key until request completion."""
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.heartbeat_interval_seconds)
                break
            except asyncio.TimeoutError:
                renewed = await self._renew_writer(token)
                if not renewed:
                    logger.warning("Writer lease renewal failed or expired prematurely", token=token)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._is_mutating_request(request):
            return await call_next(request)

        writer_token = self._generate_writer_token()
        admit_status = await self._admit_writer(writer_token)

        if admit_status < 1:
            reason = "recovery_locked" if admit_status == -2 else "maintenance_mode"
            logger.warning(
                "Mutating request rejected by admission control",
                method=request.method,
                path=request.url.path,
                reason=reason,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "maintenance",
                    "reason": reason,
                    "message": "System is undergoing maintenance or recovery quiescence. Mutations temporarily rejected.",
                    "retry_after": 30,
                },
                headers={"Retry-After": "30"},
            )

        stop_event = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(writer_token, stop_event))

        try:
            request.state.writer_token = writer_token
            response = await call_next(request)
            return response
        finally:
            stop_event.set()
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            await self._release_writer(writer_token)
