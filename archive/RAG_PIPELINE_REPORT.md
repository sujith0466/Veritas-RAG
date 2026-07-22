# RAGuard AI — RAG Pipeline Report

**Version:** 1.0.0 — Production Baseline
**Date:** 2026-07-21
**Classification:** Internal Engineering Document

---

## Executive Summary

RAGuard AI is a production-grade Enterprise Retrieval-Augmented Generation (RAG) platform engineered for reliability, observability, and hallucination prevention. This document describes the full RAG pipeline architecture as implemented in the production baseline codebase.

The pipeline is designed around three core principles:
1. **Pre-generation confidence gating** — queries are evaluated before any LLM call is made
2. **Evidence-grounded generation** — every response is anchored to retrieved knowledge chunks
3. **Post-generation reliability scoring** — responses are validated against source evidence before delivery

---

## 1. System Architecture Overview

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    RAGuard AI Platform                       │
│                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │  Auth &  │───▶│   Retrieval  │───▶│  Confidence       │  │
│  │  RBAC    │    │   Pipeline   │    │  Engine (Pre-Gen)  │  │
│  └──────────┘    └──────┬───────┘    └────────┬──────────┘  │
│                         │                     │              │
│                         ▼                     ▼              │
│               ┌──────────────────┐   ┌──────────────┐       │
│               │  Context Builder │   │  Safety Gate  │       │
│               │  (Compression,   │   │  (Hallucin.   │       │
│               │   Deduplication) │   │   Prevention) │       │
│               └────────┬─────────┘   └──────┬───────┘       │
│                        │                    │                │
│                        └────────┬───────────┘                │
│                                 ▼                            │
│                    ┌────────────────────────┐               │
│                    │   LLM Provider Manager  │               │
│                    │   (Multi-Provider       │               │
│                    │    Failover Engine)     │               │
│                    └───────────┬────────────┘               │
│                                │                            │
│                                ▼                            │
│                    ┌────────────────────────┐               │
│                    │  Post-Gen Reliability   │               │
│                    │  Scorer & Audit Logger  │               │
│                    └───────────┬────────────┘               │
└────────────────────────────────┼────────────────────────────┘
                                 │
                                 ▼
                        Grounded Response
```

---

## 2. Pipeline Stages

### Stage 1 — Authentication & Authorization

**Entry Point:** `backend/core/auth/middleware.py`

- JWT-based authentication via Supabase (dual mode: JWKS + shared secret)
- Role-Based Access Control (RBAC) with 5 roles: `admin`, `engineer`, `analyst`, `viewer`, `operator`
- Non-destructive user synchronization — internal role always preserved over JWT claims
- Audit logging for every authentication event

**Key Files:**
- `backend/core/security/jwt.py` — JWT verification (JWKS + HS256/RS256 dual mode)
- `backend/core/auth/context.py` — `UserContext`, `TokenPayload`
- `backend/core/permissions/rbac.py` — `Role` enum and access hierarchy
- `backend/services/auth/auth_service.py` — User sync and token validation

---

### Stage 2 — Hybrid Retrieval Pipeline

**Module:** `backend/modules/retrieval/`

The retrieval system implements a **hybrid search** combining dense vector search and sparse BM25 keyword search, fused using Reciprocal Rank Fusion (RRF).

#### 2.1 Dense Retrieval (Semantic Search)

- **Provider:** Qdrant (async client) via `backend/vector_db/client.py`
- **Query Encoding:** Embedding providers (OpenAI `text-embedding-3-large`, Cohere, or local BAAI/BGE models)
- **Collection:** Per-tenant namespacing with metadata filters
- **Filter DSL:** Custom filter compiler (`filter_dsl_compiler.py`) translates query filters to Qdrant filter syntax

#### 2.2 Sparse Retrieval (BM25 Keyword Search)

- **Provider:** BM25Provider (`backend/modules/retrieval/providers/sparse/bm25_provider.py`)
- **Purpose:** Handles exact keyword matches, acronyms, and named entities missed by semantic search

#### 2.3 Hybrid Fusion

- **Algorithm:** Reciprocal Rank Fusion (RRF) — `backend/modules/retrieval/services/fusion.py`
- **Formula:** `RRF(d) = Σ 1/(k + rank_i(d))` where k=60 (standard constant)
- **Purpose:** Combines dense + sparse rankings into a single unified result list without requiring score normalization

#### 2.4 Post-Retrieval Processing

| Service | Purpose |
|---------|---------|
| `dedup_engine.py` | Removes near-duplicate chunks using SimHash/Jaccard similarity |
| `context_compressor.py` | Compresses long context windows to fit LLM token budgets |
| `retrieval_service.py` | Orchestrator — coordinates all retrieval sub-services |

**Key Metrics Logged:**
- Query latency (per stage)
- Number of candidates retrieved
- Fusion score distribution
- Deduplication ratio
- Final context token count

---

### Stage 3 — Confidence Engine (Pre-Generation Gate)

**Module:** `backend/modules/confidence/`

The confidence engine evaluates retrieved context **before** any LLM call, preventing wasted compute and hallucination-prone responses.

#### Scoring Dimensions

| Scorer | Weight | Purpose |
|--------|--------|---------|
| `evidence_strength_scorer.py` | 35% | Measures semantic similarity of top-k chunks to the query |
| `coverage_analyzer.py` | 30% | Assesses whether the retrieved chunks cover the query's intent |
| `freshness_scorer.py` | 20% | Penalizes stale knowledge based on document ingestion timestamps |
| `conflict_detector.py` | 15% | Detects contradictions or conflicting claims across chunks |

#### Confidence Thresholds

```
Confidence Score >= 0.85  → PROCEED to generation
Confidence Score 0.70–0.84 → WARN (add disclaimer to response)
Confidence Score < 0.70   → ABORT generation (safety threshold)
```

When confidence is below threshold:
- Generation is skipped entirely
- A structured clarification response is returned to the user
- The event is logged to the `hallucination_prevention_log` table

---

### Stage 4 — Safety Gate (Hallucination Prevention)

**Module:** `backend/modules/retry/` (Retry Controller)

Even after the confidence engine approves a request, the safety gate enforces:

1. **Budget enforcement** — maximum retry attempts per tenant per time window (`budget_manager.py`)
2. **Retry policies** — exponential backoff with jitter for recoverable failures (`policy_engine.py`)
3. **Retry decisions** — intelligent classification of errors as recoverable vs fatal (`decision_engine.py`)
4. **Rule engine** — configurable rules for edge cases (`rule_engine.py`)

---

### Stage 5 — LLM Provider Manager (Multi-Provider Failover)

**Module:** `backend/ai/`

This is the core reliability mechanism. The system **never relies on a single LLM provider**.

#### Architecture

```
LLMProviderManager (manager.py)
    │
    ├── Priority List: ["openrouter", "gemini"]
    │
    ├── OpenRouterProvider
    │       ├── Model 1 (primary)
    │       ├── Model 2
    │       ├── Model 3
    │       ├── Model 4
    │       └── Model 5
    │
    └── GeminiProvider (fallback)
            ├── Primary: gemini-1.5-pro
            └── Lite: gemini-1.5-flash
```

#### Failover Flow

1. `LLMProviderManager.generate()` iterates the priority list
2. For each provider, `ProviderRegistry.get_provider()` instantiates the provider
3. **Within OpenRouter:** model-level failover iterates through configured free models
4. If all OpenRouter models fail → falls through to Gemini
5. If Gemini fails → `LLMProviderException` is raised (graceful error response)

#### Error Classification

| Error | Action |
|-------|--------|
| HTTP 429 (rate limit) | Skip model, try next |
| HTTP 402 (quota exceeded) | Skip model, try next |
| HTTP 5xx (provider unavailable) | Skip model, try next |
| Timeout | Skip model, try next |
| Connection failure | Skip provider, try next |
| Mid-stream failure (after tokens emitted) | Raise immediately (cannot retry) |

**Key Files:**
- `backend/ai/manager.py` — `LLMProviderManager` — inter-provider failover
- `backend/ai/providers/openrouter.py` — `OpenRouterProvider` — intra-provider model failover
- `backend/ai/providers/gemini.py` — `GeminiProvider` — fallback provider
- `backend/ai/registry.py` — `ProviderRegistry` — provider instantiation registry
- `backend/ai/factory.py` — `LLMProviderFactory` — factory abstraction

---

### Stage 6 — Context Construction

Between retrieval and generation, the pipeline builds a structured prompt:

```
System Instruction (from tenant config)
    + Retrieved Evidence Blocks (top-k chunks, cited)
    + Query
    = Final Prompt
```

Context window management:
- Token counting via provider-specific tokenizers
- Hard truncation at model max context length
- Chunk prioritization by confidence score

---

### Stage 7 — Response Generation

The LLM generates a grounded response with:
- Explicit citations back to source chunks
- Confidence-aware hedging language (when confidence is in the warning band)
- Structured output format for API consumers

---

### Stage 8 — Post-Generation Reliability Scoring

After generation:
1. **Faithfulness check** — response claims are verified against source chunks
2. **Reliability score** — numeric score [0.0, 1.0] assigned to the response
3. **Audit logging** — full request/response cycle recorded in PostgreSQL

---

## 3. Data Pipeline (Document Ingestion)

```
Raw Document
    │
    ▼
┌─────────────────────────────────────────┐
│              Ingestion Pipeline          │
│                                         │
│  ┌──────────┐    ┌──────────────────┐   │
│  │  Document │───▶│  Chunking Service │  │
│  │  Upload  │    │  (Configurable    │  │
│  │  API     │    │   Strategy)       │  │
│  └──────────┘    └────────┬─────────┘  │
│                           │             │
│                           ▼             │
│                  ┌──────────────────┐   │
│                  │  Embedding       │   │
│                  │  Service         │   │
│                  │  (Celery Worker) │   │
│                  └────────┬─────────┘  │
│                           │             │
│                   ┌───────┴──────────┐  │
│                   │                  │  │
│                   ▼                  ▼  │
│          ┌──────────────┐  ┌──────────┐ │
│          │   Qdrant     │  │ Postgres │ │
│          │ (Vectors)    │  │ (Chunks, │ │
│          └──────────────┘  │ Metadata)│ │
│                            └──────────┘ │
└─────────────────────────────────────────┘
```

### Chunking Strategies

| Strategy | Use Case |
|----------|---------|
| Fixed-size (512 tokens, 64 overlap) | Default — general documents |
| Sentence-boundary | Narrative content, policies |
| Semantic paragraph | Technical documentation |
| Code-aware | Source code repositories |

---

## 4. Data Storage Architecture

| Store | Technology | Purpose |
|-------|-----------|---------|
| Relational DB | PostgreSQL 15 (async SQLAlchemy) | Users, tenants, chunks, audit logs, query logs |
| Vector Store | Qdrant v1.7.4 | Dense embedding storage and ANN search |
| Cache | Redis (async) | Session caching, rate limiting, embedding cache |

### Database Migrations

Managed via Alembic with sequential versioning (0001 to 0011+). All migrations are backward-compatible and reversible.

---

## 5. Observability & Monitoring

### Structured Logging

- Library: `structlog` with JSON output in production
- All logs include: `tenant_id`, `trace_id`, `span_id`, `provider`, `model`, `latency_ms`
- Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### Metrics

| Metric | Description |
|--------|-------------|
| `rag.query.latency_p95` | 95th percentile query-to-response latency |
| `rag.confidence.score_avg` | Average pre-generation confidence score |
| `rag.hallucination.blocked_count` | Count of aborted generations |
| `rag.provider.failover_count` | LLM provider failover events |
| `rag.retrieval.hits` | Successful vector retrievals |
| `rag.cache.hit_ratio` | Cache hit percentage |

### Health Checks

All services expose structured health endpoints:
- `GET /api/v1/health` — Basic health (public)
- `GET /api/v1/health/detailed` — Full component health (admin-only)

Components checked: PostgreSQL, Redis, Qdrant, LLM Provider availability

---

## 6. Multi-Tenancy

RAGuard AI implements strict tenant isolation:

- **Database-level:** All queries are scoped by `tenant_id`
- **Vector-level:** Qdrant collections are namespaced per tenant
- **API-level:** Tenant context is extracted from JWT and enforced on every request
- **Cache-level:** Redis keys are prefixed with `tenant:{tenant_id}:`

---

## 7. Security Architecture

| Layer | Mechanism |
|-------|----------|
| Transport | HTTPS / TLS (enforced in production) |
| Authentication | Supabase JWT (JWKS + shared secret dual mode) |
| Authorization | RBAC with 5 roles (admin > engineer > analyst > operator > viewer) |
| Input validation | Pydantic v2 with strict typing |
| SQL injection | SQLAlchemy ORM (parameterized queries only) |
| Secret management | Environment variables (12-factor), never hardcoded |
| Rate limiting | Redis-backed per-tenant rate limits |

---

## 8. API Surface

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/token` | Exchange Supabase JWT for session |
| GET | `/api/v1/health` | Basic health check |
| GET | `/api/v1/health/detailed` | Full component health (admin) |
| POST | `/api/v1/documents/` | Upload document for ingestion |
| GET | `/api/v1/documents/` | List documents (paginated) |
| POST | `/api/v1/query/` | Execute RAG query |
| GET | `/api/v1/dashboard/executive` | Executive metrics summary |
| GET | `/api/v1/dashboard/knowledge-intelligence` | Knowledge analytics |
| GET | `/api/v1/chunks/` | List knowledge chunks |
| GET | `/api/v1/embeddings/` | List embedding jobs |
| GET | `/api/v1/vectors/` | Vector storage statistics |
| GET | `/api/v1/reliability/` | Reliability analytics |

All APIs follow REST conventions with:
- Consistent error schema: `{error_code, message, detail, timestamp}`
- Pagination via `?page=&per_page=`
- OpenAPI/Swagger documentation at `/api/v1/docs`

---

## 9. Production Readiness Checklist

| Area | Status |
|------|--------|
| Authentication & RBAC | Implemented |
| Multi-tenancy | Implemented |
| Hybrid Retrieval (Dense + Sparse + Fusion) | Implemented |
| Confidence Engine | Implemented |
| Hallucination Prevention | Implemented |
| LLM Multi-Provider Failover | Implemented |
| Structured Logging (structlog) | Implemented |
| Database Migrations (Alembic) | Implemented |
| Health Checks | Implemented |
| Error Handling | Implemented |
| Unit Tests (419 tests, 100% pass) | Passing |
| Integration Tests | Passing |
| Docker Compose | Operational |
| API Documentation | OpenAPI |

---

## 10. Future Roadmap

| Feature | Priority |
|---------|---------|
| Anthropic Claude provider | High |
| OpenAI direct provider | High |
| Azure OpenAI provider | Medium |
| Groq (ultra-fast inference) | Medium |
| Ollama (local models) | Medium |
| Together AI provider | Low |
| Graph RAG (entity relationships) | Medium |
| Re-ranking (cross-encoder) | Medium |
| Query decomposition | Medium |
| Self-RAG (iterative retrieval) | Low |

---

*This report reflects the production-frozen backend baseline as of 2026-07-21.*
