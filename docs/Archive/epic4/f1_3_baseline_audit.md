# F1.3 Baseline Audit and Gap Analysis (Redis Foundation)

## Executive Summary
A comprehensive read-only audit of the RAGuard Version 1 codebase was conducted to evaluate the existing Redis and caching architecture. The current implementation provides a basic asynchronous connection pool and client singleton, which is sufficient for simple use cases but lacks the structural foundations required for Version 2's advanced caching, distributed locking, real-time pub/sub, and streams processing.

## 1. Audit Findings

### 1.1 Configuration (`backend/core/config/redis.py`)
- **Current State:** Pydantic settings are used to configure the host, port, db (0), Celery broker (1), Celery backend (2), and test db (15).
- **Assessment:** Clean and standard. Missing configuration for retry policies (backoff) and specific timeouts for different Redis operations.

### 1.2 Client Implementation (`backend/cache/client.py`)
- **Current State:** Implements a singleton `ConnectionPool` and `Redis` client via `redis.asyncio`. Exposes `get_cache()` FastAPI dependency and `check_cache_health()`.
- **Assessment:** Solid baseline, but lacks automatic retry mechanisms, connection resilience wrappers, and metrics instrumentation.

### 1.3 Docker Compose (`docker-compose.yml`)
- **Current State:** Uses `redis:7-alpine` with `--appendonly yes` (AOF enabled). Healthcheck uses `redis-cli ping`.
- **Assessment:** Production-ready baseline for local development.

### 1.4 Missing Capabilities
- **Serialization Strategy:** No standardized JSON/Pickle serialization utilities for complex objects.
- **Key Namespace Strategy:** No centralized convention for caching keys (e.g., `tenant:{id}:cache:{key}`).
- **TTL Strategy:** No standardized TTL profiles (short, medium, long).
- **Advanced Abstractions:** Missing `CacheManager`, `DistributedLock`, `PubSubManager`, and `StreamManager`.
- **Rate Limiting:** No foundational token bucket or fixed window rate limiter scripts.

---

## 2. Gap Analysis

| Component | Class | Current State | Required State | Recommendation | Target Task |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Redis Configuration** | ⬆ Improve | Basic host/port config. | Needs retry/backoff & pool metrics config. | Add retry parameters to `RedisSettings`. | Task 1 |
| **Async Client & Pool** | ⬆ Improve | Basic singleton using `redis.asyncio`. | Needs connection resilience and retry logic. | Wrap client creation with a robust retry policy. | Task 2 |
| **Key Namespace & TTL** | 🆕 Implement New | Hardcoded strings (ad-hoc). | Structured Enum-based namespaces and TTLs. | Create `backend/cache/keys.py`. | Task 3 |
| **Serialization Utils** | 🆕 Implement New | None / Ad-hoc json dumps. | Standardized ORM/Pydantic safe serialization. | Create `backend/cache/serializers.py`. | Task 4 |
| **Cache Abstraction** | 🆕 Implement New | Direct Redis client usage. | High-level `CacheManager` with get/set/delete. | Create `backend/cache/manager.py`. | Task 5 |
| **Distributed Locks** | 🆕 Implement New | None. | Safe mutexes for background task syncing. | Create `backend/cache/locks.py`. | Task 6 |
| **Pub/Sub Foundation** | 🆕 Implement New | None. | Async generator wrappers for channel subscriptions. | Create `backend/cache/pubsub.py`. | Task 7 |
| **Streams Foundation** | 🆕 Implement New | None. | XADD/XREAD wrappers for reliable messaging. | Create `backend/cache/streams.py`. | Task 8 |
| **Rate Limiting** | 🆕 Implement New | None. | Foundation for API quotas. | Create `backend/cache/rate_limit.py`. | Task 9 |
| **Health Checks** | ✅ Reuse As-Is | `check_cache_health()` using PING. | PING is sufficient for basic health. | Reuse existing logic. | N/A |
| **Docker Compose** | ✅ Reuse As-Is | `redis:7-alpine` with AOF. | Sufficient for dev/test. | Keep as-is. | N/A |
| **Celery** | 🔴 Replace Later | Uses Celery standard integration. | Architecture calls for transition to BullMQ/ARQ. | Defer to feature targeting background workers. | Future |
