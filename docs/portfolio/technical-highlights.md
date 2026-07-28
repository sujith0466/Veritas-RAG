# RAGuard AI — Technical Highlights

## 1. Clean Architecture & DDD

Every module follows a strict three-layer pattern:
```
FastAPI Router -> Service Layer -> Repository Layer
```
No business logic leaks into routers. No direct DB calls from services.
Provider interfaces ensure zero coupling to specific LLM vendors.

## 2. Hybrid Retrieval with RRF

RAGuard combines Qdrant dense vector search with BM25 sparse retrieval,
merging results via Reciprocal Rank Fusion (RRF). Deduplication engine
removes semantically equivalent chunks using cosine similarity thresholds.

## 3. Confidence-Driven Architecture

The Confidence Engine computes a composite score from:
- **Coverage Score** — What percentage of the query is answered?
- **Conflict Score** — Are retrieved documents contradicting each other?
- **Evidence Strength** — How strongly do sources support the answer?
- **Freshness Score** — How recent is the retrieved evidence?

## 4. Async-First Design

All database queries use SQLAlchemy 2.x async sessions with asyncpg.
All HTTP calls use httpx with async context managers.
All retrieval operations are fully non-blocking.

## 5. Enterprise Security

- **DLP Engine**: Regex-based PII redaction before LLM transit (<1ms overhead).
- **RBAC**: Multi-tenant role enforcement at every API endpoint.
- **Audit Logging**: Immutable structured JSON audit trails.
- **Chaos Engineering**: Synthetic fault injection (production-fenced).

## 6. Observability

- **Prometheus**: Custom counters and histograms on every domain event.
- **OpenTelemetry**: W3C trace context propagated across all service boundaries.
- **Structured Logging**: JSON logs with embedded trace_id for correlation.

## 7. Self-Healing Production Resilience

- **Circuit Breaker**: Automatic open/close based on error rate thresholds.
- **Model Rotation**: Falls back through LLM_PRIORITY_LIST on provider failure.
- **Region Failover**: Active-passive failover via RegionRouter (Phase 20).
- **Chaos Injection**: Simulates 503s and latency spikes in staging environments.

## 8. Enterprise Intelligence

- **Threshold Optimizer**: Adjusts similarity and confidence thresholds based
  on trailing query analytics without operator intervention.
- **Index Advisor**: Recommends vector re-clustering based on latency metrics.
- **Feedback Loop**: Accepts implicit (dwell time) and explicit (thumbs up/down)
  user signals to continuously improve relevance.
