# RAGuard AI — System Architecture

## Architectural Principles

- **Clean Architecture**: Domain logic never depends on infrastructure.
- **Domain-Driven Design**: Each bounded context owns its data and behavior.
- **Provider Abstraction**: LLMs and vector DBs accessed through interfaces.
- **Event-Driven**: Cross-module communication via async event dispatchers.
- **Dependency Injection**: All services injected via FastAPI `Depends()`.

## Layer Overview

```
Presentation  : FastAPI Routers, Pydantic DTOs, Middleware
Domain        : Services, Business Logic, Domain Models
Infrastructure: SQLAlchemy ORM, Redis, Qdrant, LLM Providers
```

## Module Map

| Module | Responsibility |
|--------|---------------|
| `backend/modules/query_intelligence` | OCR, normalization, intent detection |
| `backend/modules/retrieval` | Hybrid dense+sparse search, fusion, dedup |
| `backend/modules/confidence` | Coverage, conflict, evidence scoring |
| `backend/modules/retry` | Budget management, rewrite, clarification |
| `backend/modules/generation` | LLM orchestration, grounded output |
| `backend/modules/reflection` | Self-critique and iterative correction |
| `backend/modules/validation` | NLI claim checking, citation verification |
| `backend/modules/knowledge_health` | Index health, parity checks |
| `backend/modules/evaluation` | Golden datasets, benchmarking |
| `backend/modules/dashboard` | Executive views, WebSocket live feeds |
| `backend/modules/alerts` | Rule engine, multi-channel dispatchers |
| `backend/modules/reliability` | Self-healing governor, model rotation |
| `backend/modules/analytics` | ROI, token quotas, forecasting |
| `backend/core/chaos` | Controlled chaos engineering (non-prod) |
| `backend/core/resilience` | Multi-region failover, circuit breakers |
| `backend/modules/observability` | Prometheus metrics, OTEL tracing |
| `backend/modules/security` | DLP engine, compliance auditor |
| `backend/modules/intelligence` | Threshold optimization, feedback loops |
| `backend/modules/marketplace` | Tenant config bundles, SHA-256 signing |

## Data Flow (Happy Path)

```
User Request
  -> TelemetryMiddleware (trace context)
  -> SecurityInterceptor (DLP redaction)
  -> QueryIntelligence (normalize + entity extraction)
  -> HybridRetrieval (dense + sparse + RRF + dedup)
  -> ConfidenceEngine (coverage + conflict scoring)
  -> [Low Confidence] -> RetryController (rewrite / clarify)
  -> Generation (grounded LLM call)
  -> Reflection (self-critique)
  -> Validation (NLI + citations)
  -> MetricsRegistry (Prometheus counter increment)
  -> Response
```
