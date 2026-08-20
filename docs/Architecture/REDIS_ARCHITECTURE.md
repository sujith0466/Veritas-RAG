# RAGuard V2 Redis Architecture

This document formalizes the caching, messaging, and locking architecture for RAGuard Version 2.

## 1. Redis Database Usage Policy

**Official Strategy: Single Database with Strict Namespacing**
- **Use DB 0** for all primary application data (Cache, Pub/Sub, Streams, Locks, Rate Limiting).
- **Separate concerns** using strict key namespaces instead of multiple logical databases.
- Reserve other logical databases only where absolutely necessary (e.g., DB 15 for isolated integration tests).

**Why Key Namespacing is Preferred:**
1. **Cluster Compatibility:** Redis Cluster does not support multiple logical databases (only DB 0 is allowed). Utilizing strict namespaces ensures the application is natively cluster-ready for future scaling.
2. **Observability:** Metric tools and monitoring dashboards can easily aggregate and slice data based on key prefixes.
3. **Simplicity:** Connection pools are vastly simplified when communicating with a single database, reducing overhead and the risk of connection leaks across multiple DB boundaries.

## 2. Key Namespace Strategy

To prevent collisions and enable precise invalidation, every key must be constructed using the `CacheKeyBuilder`.

**Format:** `rg:v2:{tenant}:{domain}:{entity}:{id}`

*   `rg:v2`: The static system and version identifier.
*   `tenant`: The UUID of the tenant, or `global` for system-wide configuration.
*   `domain`: The bounded context (e.g., `auth`, `knowledge`, `chat`).
*   `entity`: The type of data (e.g., `user`, `session`, `lock`, `ratelimit`).
*   `id`: The unique identifier of the entity.

## 3. TTL Policy

Raw integer TTLs are prohibited. All cached data must use a predefined `TTLProfile` Enum:
- `TRANSIENT`: 60 seconds (ephemeral data, rate limits)
- `SHORT`: 300 seconds (temporary auth states)
- `MEDIUM`: 3600 seconds (frequently accessed static data)
- `LONG`: 86400 seconds (24 hours - standard sessions)
- `MAXIMUM`: 604800 seconds (7 days - max allowed cache lifetime)

## 4. Serialization Strategy

- **JSON / UTF-8 Only:** All complex objects must be serialized to JSON UTF-8 strings. Pickle is strictly prohibited for security (RCE risks) and cross-language compatibility.
- **Data Types:** The `CacheJSONEncoder` natively intercepts and serializes:
  - `datetime`: Forced to UTC timezone and encoded as ISO-8601 strings.
  - `UUID`: Encoded as standard strings.
  - `BaseModel`: Pydantic V2 models are cleanly dumped using `model_dump(mode="json")`.

## 5. Connection Lifecycle & Retry Architecture

- **Singleton Pool:** Connections are managed via a singleton async `ConnectionPool`.
- **Generic Retry Utility:** Resilience is handled at the infrastructure layer using an exponential backoff decorator (`with_retry`). This decorator is independent of third-party libraries (e.g., `tenacity`) and is shared across Redis, PostgreSQL, and OpenRouter connections.
- **Failures:** Transient network failures trigger exponential backoff. If max retries are exceeded, the failure bubbles up as an `InfrastructureError`.

## 6. Infrastructure Primitives

The codebase strictly enforces the separation of infrastructure mechanisms from business logic.

- **CacheManager:** Provides generic `get`, `set`, and `delete` wrappers enforcing keys, TTLs, and serialization.
- **Distributed Locks:** Uses `SET NX EX` wrapped in an async context manager with auto-release via Lua scripts to ensure safe multi-worker concurrency.
- **Pub/Sub:** Provides infrastructure-level `publish` and `subscribe` generators for transient, fire-and-forget real-time notifications.
- **Streams:** Provides `xadd` and `xread` abstractions for reliable event logs and messaging that require persistence.
- **Rate Limiting:** Implements Fixed Window limits using Redis `INCR` and `EXPIRE` evaluated via Lua to prevent race conditions.

## 7. Observability and Health

- **Health Checks:** Evaluates `PING`, round-trip latency, connection status, and reconnect success.
- **Metrics Foundation:** Tracks hits, misses, retries, and reconnects internally (exported to Prometheus & OpenTelemetry in Epic 14).
