# PHASE_5_IMPLEMENTATION_PLAN.md
# RAGuard AI — Phase 5: Hybrid Retrieval Engine (Production Grade)

**Version**: 1.0.0  
**Date**: 2026-07-20  
**Author**: Principal Software Architect  
**Status**: PLANNING — Awaiting Approval  
**Depends On**: Phases 0–4 (COMPLETED & FROZEN)

---

## 1. Executive Summary

Phase 5 delivers the **production-grade Hybrid Retrieval Engine** for RAGuard AI. While Phase 2 introduced the foundational `RetrievalOrchestrator` skeleton with Dense + Sparse + RRF + Cross-Encoder capabilities, Phase 5 hardens these components to enterprise production standards: configurable metadata filtering, context compression, deterministic duplicate removal, query-time tenant isolation, and comprehensive audit logging.

The Phase 5 retrieval pipeline becomes the **canonical data contract boundary** between the ingestion layer (Phases 1–4) and the downstream Retrieval Reliability (Phase 6), Retry Controller (Phase 7), Query Rewrite (Phase 8), Clarification (Phase 9), and Grounded Answer Generation (Phase 10) layers.

---

## 2. Phase Objectives

1. Deliver production-hardened **Dense Retrieval** with proper embedding normalization, HNSW parameter tuning, and score clamping.
2. Deliver production-hardened **Sparse Retrieval (BM25)** with persistent tenant index storage, incremental updates, and proper term frequency normalization.
3. Implement configurable **Metadata Filtering** with structured filter DSL, tenant namespace enforcement, and document-level access controls.
4. Harden **Reciprocal Rank Fusion (RRF)** with configurable `k` parameter per query, score normalization, and audit trail.
5. Implement production **Cross-Encoder Reranking** with batched inference, timeout guards, and graceful degradation.
6. Implement **Context Compression** — LLM-guided chunk compression and sentence extraction to minimize irrelevant context sent downstream.
7. Implement deterministic **Duplicate Removal** using SHA-256 content fingerprinting and token-overlap Jaccard similarity.
8. Expose complete REST API with Prometheus metrics integration and OpenTelemetry span coverage.

---

## 3. Business Goals

- **Retrieval Precision**: Improve evidence precision@k by combining dense semantic and sparse keyword signals.
- **Response Quality**: Ensure downstream generation receives only the highest-quality, non-redundant evidence.
- **Tenant Isolation**: Guarantee that cross-tenant data leakage is architecturally impossible at the retrieval layer.
- **Audit Compliance**: Every retrieval execution is fully traceable with stage-level latency, candidate counts, and filter parameters logged.
- **Operational Reliability**: The retrieval engine must remain functional under partial provider failures through graceful degradation.

---

## 4. Technical Goals

- All retrieval stages are async-native and individually instrumented with OpenTelemetry spans.
- Metadata filters expressed as a structured `FilterDSL` (not raw dicts) with compile-time Pydantic validation.
- BM25 index storage backed by Redis (in-memory) with periodic PostgreSQL snapshots for durability.
- Cross-encoder reranking uses batched sentence-pair scoring with configurable `batch_size` and `timeout_ms`.
- Context compression achieves at least 30% token reduction without content loss.
- Duplicate removal is deterministic: same input always produces same output (SHA-256 fingerprinting).
- All stage latency breakdowns are recorded at sub-millisecond precision.

---

## 5. Scope

| Component | Included in Phase 5 |
|---|---|
| Dense Retrieval (Qdrant HNSW) | ✅ |
| Sparse Retrieval (BM25 / TF-IDF) | ✅ |
| Metadata Filtering (FilterDSL) | ✅ |
| Reciprocal Rank Fusion (RRF) | ✅ |
| Cross-Encoder Reranking | ✅ |
| Context Compression | ✅ |
| Duplicate Removal (SHA-256 + Jaccard) | ✅ |
| Retrieval REST API v2 | ✅ |
| Prometheus Metrics (retrieval-specific) | ✅ |
| OpenTelemetry Span Coverage (all stages) | ✅ |
| BM25 Index Redis Persistence | ✅ |
| Unit & Integration Tests | ✅ |

---

## 6. Out of Scope

- Confidence evaluation or scoring (→ Phase 6)
- Query rewrite or HyDE strategies (→ Phase 8)
- Clarification question generation (→ Phase 9)
- LLM answer generation (→ Phase 10)
- Circuit breaker or reliability failover (→ Phase 6)
- Frontend UI dashboards

---

## 7. PRD Alignment

| PRD Requirement | Phase 5 Component |
|---|---|
| FR-RET-1: Hybrid dense + sparse retrieval | Dense + Sparse Orchestrator |
| FR-RET-2: Tenant-scoped metadata filtering | FilterDSL + tenant enforcement |
| FR-RET-3: Reciprocal Rank Fusion | FusionEngine (production hardened) |
| FR-RET-4: Cross-encoder reranking | CrossEncoderReranker (batched) |
| FR-RET-5: Near-duplicate deduplication | SHA-256 + Jaccard DedupEngine |
| NFR-PERF-1: P95 retrieval latency < 400ms | Async gather + timeout guards |
| NFR-SEC-1: Tenant isolation | FilterDSL tenant_id enforcement |
| NFR-OBS-1: Full observability | OTel + Prometheus on every stage |

---

## 8. Solution Overview Alignment

Phase 5 maps to the **Evidence Retrieval Layer** of the RAGuard AI Solution Overview. The phase ensures the retrieval tier operates as a closed, testable, independently deployable subsystem that can be replaced (per ADR-006) without affecting upstream or downstream modules.

---

## 9. Architecture Alignment

- Follows **Domain-Oriented Modular Architecture** (ADR-005): all retrieval logic under `backend/modules/retrieval/`.
- Follows **Provider Abstraction Layer** (ADR-006): dense, sparse, and reranker providers behind abstract interfaces in `backend/providers/`.
- Follows **Hybrid Retrieval Strategy** (ADR-002): Dense + Sparse + RRF + Rerank pipeline is architecturally mandated.
- Aligns with **Qdrant Vector Database** (ADR-004): INT8 quantization, payload filter indexes.

---

## 10. Dependency Analysis

### Upstream Dependencies (must be completed)
| Phase | Component | Required By Phase 5 |
|---|---|---|
| Phase 2 | `DocumentChunk` ORM model | BM25 index construction |
| Phase 2 | `EmbeddingJob` / `ChunkEmbedding` | Dense vector search |
| Phase 2 | Qdrant `VectorIndexMetadata` | Collection name resolution |
| Phase 2 | `RetrievalOrchestrator` (baseline) | Extension target |
| Phase 4 | `ObservabilityMiddleware` | Prometheus instrumentation |
| Phase 4 | OpenTelemetry Tracer | Span coverage |

### Downstream Consumers (will depend on Phase 5)
| Phase | Component | Consumes from Phase 5 |
|---|---|---|
| Phase 6 | ConfidenceEngine | `RetrievalResultDTO` + `CompressedContextDTO` |
| Phase 7 | RetryController | Re-invokes retrieval on retry |
| Phase 8 | QueryRewrite | Re-invokes retrieval post-rewrite |
| Phase 10 | AnswerGenerator | `CompressedContextDTO` |

---

## 11. Existing Codebase Review

### What Already Exists (Baseline — DO NOT Duplicate)

| Component | Location | Status |
|---|---|---|
| `RetrievalOrchestrator` | `backend/modules/retrieval/services/retrieval_service.py` | Baseline stub — Phase 5 hardens |
| `FusionEngine` | `backend/modules/retrieval/services/fusion.py` | Phase 5 adds persistence |
| `SearchRequestDTO` | `backend/modules/retrieval/schemas/retrieval_dto.py` | Extend with `FilterDSL` |
| `CandidatePointDTO`, `RankedEvidenceDTO` | Same | Extend with compression fields |
| `BM25SparseSearchProvider` | `backend/modules/retrieval/providers/sparse/` | Phase 5 adds Redis persistence |
| `CohereRerankerProvider` | `backend/modules/retrieval/providers/reranker/` | Phase 5 adds batching + timeout |
| `RetrievalQueryLog` ORM model | `backend/modules/retrieval/models/` | Phase 5 extends with filter_dsl field |
| Alembic migration `0006` | `alembic/versions/` | Phase 5 adds migration `0009` |

### What Must Be Extended (Not Rebuilt)

- `SearchRequestDTO`: Add `filter_dsl: FilterDSL | None` field.
- `RankedEvidenceDTO`: Add `compressed_content: str | None` and `compression_ratio: float | None`.
- `RetrievalOrchestrator.execute_hybrid_search()`: Wire `FilterDSL` → Qdrant payload filters.
- `BM25SparseSearchProvider`: Add Redis-backed index persistence.

---

## 12. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Phase 5: Hybrid Retrieval Engine              │
├──────────────────────────┬──────────────────────────────────────┤
│  /api/v1/retrieval/      │  FastAPI Router (routes.py v2)       │
│    search                │                                      │
│    sandbox               │  ← FilterDSL validated at boundary   │
│    compress              │                                      │
├──────────────────────────┴──────────────────────────────────────┤
│                   RetrievalOrchestrator (v2)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Dense Stage  │  │ Sparse Stage │  │   FusionEngine (RRF)  │  │
│  │  Qdrant HNSW │  │ BM25 + Redis │  │   k=60 configurable   │  │
│  │  INT8 quant  │  │  persistence │  │   + Deduplication v2  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬────────────┘  │
│         └─────────asyncio.gather──────────────────┘              │
│                            │                                     │
│              ┌─────────────▼──────────────┐                      │
│              │   CrossEncoderReranker (v2) │                      │
│              │   batched, timeout-guarded  │                      │
│              └─────────────┬──────────────┘                      │
│                            │                                     │
│              ┌─────────────▼──────────────┐                      │
│              │   ContextCompressor         │                      │
│              │   LLM-guided compression    │                      │
│              └─────────────┬──────────────┘                      │
│                            │                                     │
│                    RetrievalResultDTOv2                          │
└─────────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │   Observability Layer               │
          │   OTel spans + Prometheus metrics   │
          └────────────────────────────────────┘
```

---

## 13. Low-Level Design

### FilterDSL Design

```
FilterDSL:
  tenant_id: str (required, enforced)
  document_ids: list[UUID] | None
  source_types: list[str] | None    # e.g. ["pdf", "markdown"]
  date_range: DateRangeFilter | None
    start: datetime
    end: datetime
  metadata_eq: dict[str, str] | None   # exact match
  metadata_contains: dict[str, str] | None  # substring match
```

FilterDSL is compiled to Qdrant `Filter` objects at the `RetrievalOrchestrator` boundary. `tenant_id` is always injected server-side from JWT claims — never from client request body.

### Context Compression Algorithm

1. Receive `top_k` `RankedEvidenceDTO` items post-reranking.
2. For each item, extract the **most query-relevant sentences** using TF-IDF sentence ranking against the query.
3. Retain sentences with relevance score ≥ 0.3 threshold.
4. Cap compressed content at `max_tokens=512` per chunk.
5. Record `compression_ratio = len(compressed) / len(original)`.
6. If LLM provider is available, use a lightweight prompt: `"Extract the top 3 most relevant sentences from the following passage for the query: {query}"`.

### Duplicate Removal Algorithm (v2)

```
Phase 1 — SHA-256 Exact Dedup:
  For each candidate, compute SHA-256(normalize(content))
  Drop any candidate whose fingerprint was already seen

Phase 2 — Jaccard Near-Dedup:
  For candidates with Jaccard(token_set_A, token_set_B) > threshold (default 0.92)
  Keep the candidate with higher rerank_score

Phase 3 — Semantic Near-Dedup:
  For top-30 candidates, compute cosine similarity between embedding vectors
  If cosine_similarity > 0.95, keep higher-ranked candidate
```

---

## 14. Component Design

### 14.1 DenseRetrievalStage (new)
```
class DenseRetrievalStage:
  - embed_query(query: str) → list[float]
  - search_qdrant(vector, filter_conditions, limit) → list[CandidatePointDTO]
  - normalize_scores(candidates) → list[CandidatePointDTO]
  - with OTel span: "retrieval.dense"
```

### 14.2 SparseRetrievalStage (extends existing)
```
class SparseRetrievalStage (extends BM25SparseSearchProvider):
  + persist_index_to_redis(tenant_id) → None
  + load_index_from_redis(tenant_id) → bool
  + incremental_update(new_chunks) → None
  - with OTel span: "retrieval.sparse"
```

### 14.3 FusionEngine (extends existing)
```
class FusionEngine (extended):
  - execute_rrf_fusion(dense, sparse, k=60) → list[RankedEvidenceDTO]
  + configurable_k(options: FusionOptionsDTO)
  + audit_trail: FusionAuditDTO (score breakdown per candidate)
  - with OTel span: "retrieval.rrf_fusion"
```

### 14.4 DedupEngine (new — extracted from FusionEngine)
```
class DedupEngine:
  - sha256_dedup(candidates) → list[RankedEvidenceDTO]
  - jaccard_dedup(candidates, threshold=0.92) → list[RankedEvidenceDTO]
  - semantic_dedup(candidates, threshold=0.95) → list[RankedEvidenceDTO]
  - full_dedup_pipeline(candidates, options) → list[RankedEvidenceDTO]
  - with OTel span: "retrieval.deduplication"
```

### 14.5 CrossEncoderReranker (extends existing)
```
class CrossEncoderReranker (extends BaseRerankerProvider):
  + batch_size: int = 16
  + timeout_ms: int = 2000
  + fallback_to_rrf_on_timeout: bool = True
  - rerank_batched(query, candidates, top_k) → list[RankedEvidenceDTO]
  - with OTel span: "retrieval.reranking"
```

### 14.6 ContextCompressor (new)
```
class ContextCompressor:
  - compress_candidates(query, candidates, max_tokens_per_chunk) → list[CompressedEvidenceDTO]
  - sentence_relevance_score(sentence, query) → float
  - truncate_to_token_budget(text, max_tokens) → str
  - with OTel span: "retrieval.compression"
```

### 14.7 FilterDSLCompiler (new)
```
class FilterDSLCompiler:
  - compile(filter_dsl: FilterDSL, tenant_id: str) → QdrantFilter
  - enforce_tenant_namespace(filter, tenant_id) → QdrantFilter
  - validate_no_cross_tenant_leak(filter, request_tenant_id) → None
```

---

## 15. Module Responsibilities

| Component | Responsibility | Layer |
|---|---|---|
| `FilterDSLCompiler` | Translate `FilterDSL` → Qdrant filter objects with tenant enforcement | Service |
| `DenseRetrievalStage` | Embed query + search Qdrant HNSW + normalize scores | Service |
| `SparseRetrievalStage` | BM25 search + Redis index persistence + incremental updates | Service |
| `FusionEngine` | RRF merge + audit trail | Service |
| `DedupEngine` | SHA-256 + Jaccard + Semantic deduplication pipeline | Service |
| `CrossEncoderReranker` | Batched sentence-pair scoring with timeout guard | Provider |
| `ContextCompressor` | TF-IDF sentence extraction + token budget management | Service |
| `RetrievalOrchestrator` | Coordinate all stages; expose `execute_hybrid_search_v2()` | Orchestrator |
| `RetrievalRepository` | Persist query logs + filter DSL snapshots | Repository |
| API Routes | Validate `FilterDSL` at boundary; inject `tenant_id` from JWT | API |

---

## 16. Data Flow

```
Client Request (query + FilterDSL)
        │
        ▼
API Layer: JWT → tenant_id injected; FilterDSL validated
        │
        ▼
FilterDSLCompiler → QdrantFilter (tenant_id enforced)
        │
        ├──────────────────┬───────────────────┐
        ▼                  ▼                   │
DenseRetrievalStage   SparseRetrievalStage     │
(Qdrant + OTel)       (BM25+Redis + OTel)     │
        │                  │                   │
        └──────asyncio.gather───────────────────┘
                          │
                          ▼
                    FusionEngine (RRF + audit)
                          │
                          ▼
                    DedupEngine (SHA-256 → Jaccard → Semantic)
                          │
                          ▼
              CrossEncoderReranker (batched, timeout-guarded)
                          │
                          ▼
                  ContextCompressor (sentence extraction)
                          │
                          ▼
              RetrievalResultDTOv2 → downstream phases
                          │
                          ▼
        RetrievalRepository.log_query_execution()
        Prometheus metrics record
        OTel span close
```

---

## 17. Sequence Flow

```
1. Client → POST /api/v1/retrieval/search
2. Route handler validates request; extracts tenant_id from JWT
3. FilterDSLCompiler.compile(filter_dsl, tenant_id) → QdrantFilter
4. asyncio.gather(dense_task, sparse_task)
   4a. DenseRetrievalStage: embed_query → search_qdrant(filter) → [CandidatePointDTO]
   4b. SparseRetrievalStage: load_index_from_redis → bm25_search → [CandidatePointDTO]
5. FusionEngine.execute_rrf_fusion(dense, sparse, k)
6. DedupEngine.full_dedup_pipeline(merged, options)
7. CrossEncoderReranker.rerank_batched(query, deduped[:30], top_k)
8. ContextCompressor.compress_candidates(query, reranked, max_tokens)
9. RetrievalOrchestrator constructs RetrievalResultDTOv2
10. asyncio.create_task(RetrievalRepository.log_query_execution())
11. Response returned to caller
```

---

## 18. Folder Structure Changes

```
backend/modules/retrieval/
├── api/
│   ├── __init__.py
│   ├── dependencies.py            [MODIFY] add FilterDSL injection
│   └── routes.py                  [MODIFY] add compress endpoint; v2 search
├── schemas/
│   ├── __init__.py
│   ├── errors.py                  [MODIFY] add FilterDSLError (RET_006)
│   ├── retrieval_dto.py           [MODIFY] extend with FilterDSL, CompressedEvidenceDTO
│   └── filter_dsl.py              [NEW] FilterDSL, DateRangeFilter, FusionOptionsDTO
├── services/
│   ├── retrieval_service.py       [MODIFY] wire FilterDSLCompiler; add v2 method
│   ├── fusion.py                  [MODIFY] add audit trail + configurable k
│   ├── dedup_engine.py            [NEW] DedupEngine (SHA-256 + Jaccard + Semantic)
│   ├── context_compressor.py      [NEW] ContextCompressor
│   └── filter_dsl_compiler.py    [NEW] FilterDSLCompiler
├── providers/
│   ├── dense/
│   │   ├── __init__.py
│   │   ├── base.py                [NEW] BaseDenseRetrievalProvider
│   │   └── qdrant_provider.py     [NEW] QdrantDenseProvider (extracted+hardened)
│   ├── sparse/
│   │   ├── base.py                [MODIFY] add persist/load methods
│   │   ├── bm25_provider.py       [MODIFY] add Redis persistence
│   │   └── factory.py             [MODIFY] factory registration
│   └── reranker/
│       ├── base.py                [MODIFY] add batch_size, timeout_ms params
│       ├── cohere_provider.py     [MODIFY] add batched inference
│       └── local_provider.py      [MODIFY] add batched inference
├── models/
│   └── retrieval_query_log.py     [MODIFY] add filter_dsl_json, compression_ratio
├── repositories/
│   └── retrieval_repository.py    [MODIFY] add filter DSL persistence
├── events/                        [existing]
└── workers/                       [existing]
```

---

## 19. File Creation Plan

| File | Type | Purpose |
|---|---|---|
| `schemas/filter_dsl.py` | NEW | `FilterDSL`, `DateRangeFilter`, `FusionOptionsDTO`, `CompressionOptionsDTO` |
| `services/dedup_engine.py` | NEW | `DedupEngine` — 3-phase deduplication pipeline |
| `services/context_compressor.py` | NEW | `ContextCompressor` — TF-IDF + LLM sentence extraction |
| `services/filter_dsl_compiler.py` | NEW | `FilterDSLCompiler` — translate to Qdrant filter objects |
| `providers/dense/__init__.py` | NEW | Package init |
| `providers/dense/base.py` | NEW | `BaseDenseRetrievalProvider` abstract interface |
| `providers/dense/qdrant_provider.py` | NEW | `QdrantDenseProvider` with HNSW tuning |
| `tests/unit/backend/modules/retrieval/test_dedup_engine.py` | NEW | DedupEngine tests |
| `tests/unit/backend/modules/retrieval/test_context_compressor.py` | NEW | Compressor tests |
| `tests/unit/backend/modules/retrieval/test_filter_dsl.py` | NEW | FilterDSL + compiler tests |

---

## 20. Database Changes

### Alembic Migration: `0009_retrieval_v2_schema.py`

```sql
-- Extend retrieval_query_log table
ALTER TABLE retrieval_query_logs
  ADD COLUMN filter_dsl_json    JSONB,
  ADD COLUMN compression_ratio  FLOAT,
  ADD COLUMN dedup_removed_count INTEGER DEFAULT 0,
  ADD COLUMN rerank_timeout_triggered BOOLEAN DEFAULT FALSE;

-- Index for filter_dsl querying
CREATE INDEX idx_retrieval_query_logs_filter_dsl
  ON retrieval_query_logs USING gin(filter_dsl_json);
```

### No new tables required in Phase 5.

---

## 21. API Design

### 21.1 POST /api/v1/retrieval/search (v2 extended)

**Request**:
```json
{
  "query": "What is the return policy for enterprise contracts?",
  "top_k": 10,
  "limit_dense": 50,
  "limit_sparse": 50,
  "rrf_k": 60,
  "dedup_similarity_threshold": 0.92,
  "compression_options": {
    "enabled": true,
    "max_tokens_per_chunk": 512,
    "min_relevance_score": 0.3
  },
  "filter_dsl": {
    "document_ids": ["uuid-1", "uuid-2"],
    "source_types": ["pdf"],
    "date_range": {
      "start": "2025-01-01T00:00:00Z",
      "end": "2026-01-01T00:00:00Z"
    },
    "metadata_eq": {"department": "legal"}
  }
}
```

**Response**: `RetrievalResultDTOv2`
```json
{
  "query_text": "...",
  "tenant_id": "...",
  "correlation_id": "...",
  "final_evidence": [
    {
      "chunk_id": "...",
      "content": "...",
      "compressed_content": "...",
      "compression_ratio": 0.64,
      "rrf_score": 0.0312,
      "rerank_score": 0.91,
      "final_rank": 1,
      "matched_sources": ["dense", "sparse"],
      "metadata": {}
    }
  ],
  "stage_latencies": {
    "dense_ms": 45.2,
    "sparse_ms": 12.1,
    "rrf_fusion_ms": 2.8,
    "dedup_ms": 1.4,
    "rerank_ms": 87.6,
    "compression_ms": 24.3,
    "total_ms": 173.4
  },
  "dedup_removed_count": 4,
  "filter_applied": true
}
```

### 21.2 POST /api/v1/retrieval/compress (NEW)

**Purpose**: Compress existing evidence without re-running retrieval.  
**Request**: `{ "query": str, "evidence": list[RankedEvidenceDTO], "max_tokens": int }`  
**Response**: `{ "compressed_evidence": list[CompressedEvidenceDTO], "compression_ratios": list[float] }`

### 21.3 GET /api/v1/retrieval/metrics (existing — extended)

Extended with: `dedup_removal_rate`, `compression_ratio_avg`, `rerank_timeout_rate`, `filter_usage_rate`.

---

## 22. Configuration Changes

### New Settings Block in `backend/core/config/settings.py`

```python
class RetrievalSettings(BaseModel):
    dense_limit_default: int = 50
    sparse_limit_default: int = 50
    rrf_k_default: int = 60
    dedup_jaccard_threshold: float = 0.92
    dedup_semantic_threshold: float = 0.95
    rerank_batch_size: int = 16
    rerank_timeout_ms: int = 2000
    rerank_fallback_to_rrf: bool = True
    compression_enabled: bool = True
    compression_max_tokens: int = 512
    compression_min_relevance: float = 0.3
    bm25_redis_ttl_seconds: int = 86400
    bm25_snapshot_interval_seconds: int = 3600
```

---

## 23. Environment Variables

```bash
# Phase 5 Retrieval Configuration
RETRIEVAL_DENSE_LIMIT_DEFAULT=50
RETRIEVAL_SPARSE_LIMIT_DEFAULT=50
RETRIEVAL_RRF_K_DEFAULT=60
RETRIEVAL_DEDUP_JACCARD_THRESHOLD=0.92
RETRIEVAL_DEDUP_SEMANTIC_THRESHOLD=0.95
RETRIEVAL_RERANK_BATCH_SIZE=16
RETRIEVAL_RERANK_TIMEOUT_MS=2000
RETRIEVAL_COMPRESSION_ENABLED=true
RETRIEVAL_COMPRESSION_MAX_TOKENS=512
RETRIEVAL_BM25_REDIS_TTL_SECONDS=86400
```

---

## 24. Security Considerations

1. **Tenant Isolation**: `tenant_id` is always extracted from the validated JWT token in the API dependency layer. It is never accepted from the request body's `filter_dsl`. The `FilterDSLCompiler` always enforces `tenant_id` at compile time.
2. **Filter Injection Prevention**: `FilterDSL` fields are strictly typed Pydantic models. No raw dict pass-through to Qdrant.
3. **Content Sanitization**: Compressed context is re-sanitized before downstream use to prevent prompt injection via retrieved content.
4. **Rate Limiting**: Retrieval endpoints enforce per-tenant rate limits via the existing `RateLimitException` middleware.
5. **PII Protection**: `metadata_eq` filters cannot expose cross-tenant metadata.

---

## 25. Performance Considerations

1. Dense and sparse stages run concurrently (`asyncio.gather`) — adds zero latency.
2. Cross-encoder reranking operates on ≤30 candidates (ADR-M4-002 bounded) to cap compute cost.
3. Reranking has hard `timeout_ms=2000` with automatic fallback to RRF ordering.
4. BM25 indexes are in-memory in Redis (O(1) load). Disk snapshots are async background tasks.
5. Context compression runs on the final top_k (≤10) items, not the full candidate pool.
6. FilterDSL compilation is in-memory (no I/O) — microsecond overhead.

---

## 26. Scalability Considerations

1. `RetrievalOrchestrator` is stateless — horizontally scalable without coordination.
2. BM25 Redis index is per-tenant namespace — scales by adding Redis cluster shards.
3. Qdrant collection sharding follows Qdrant's native horizontal scaling model.
4. Context compression can be offloaded to a dedicated worker via Celery if LLM-based.
5. Cross-encoder reranking can be offloaded to a dedicated GPU inference endpoint behind the provider abstraction.

---

## 27. Logging Strategy

```python
# Structured log fields per stage:
logger.info("retrieval.dense.complete",
    tenant_id=tenant_id,
    correlation_id=correlation_id,
    candidates_found=len(candidates),
    duration_ms=duration_ms,
    filter_applied=bool(filter_dsl)
)

logger.info("retrieval.dedup.complete",
    removed_count=removed,
    jaccard_removed=jaccard_count,
    sha256_removed=sha256_count
)

logger.warning("retrieval.rerank.timeout",
    timeout_ms=timeout_ms,
    fallback="rrf_ordering"
)
```

---

## 28. Monitoring Strategy

### New Prometheus Metrics (Phase 5)

```
raguard_retrieval_dense_duration_seconds (histogram)
raguard_retrieval_sparse_duration_seconds (histogram)
raguard_retrieval_rrf_fusion_duration_seconds (histogram)
raguard_retrieval_dedup_removed_total (counter, labels: method)
raguard_retrieval_rerank_duration_seconds (histogram)
raguard_retrieval_rerank_timeouts_total (counter)
raguard_retrieval_compression_ratio (histogram)
raguard_retrieval_filter_applied_total (counter, labels: filter_type)
```

### Grafana Panels (additive to Phase 4 dashboard)

- Stage-by-stage latency waterfall (P50/P95 per stage)
- Deduplication removal rate
- Reranking timeout rate
- Compression ratio distribution

---

## 29. Error Handling Strategy

| Error Code | Exception | HTTP Status | Description |
|---|---|---|---|
| RET_001 | `InvalidQueryError` | 400 | Query empty or exceeds 2000 chars |
| RET_002 | `FilterDSLValidationError` | 400 | Malformed FilterDSL |
| RET_003 | `TenantViolationError` | 403 | filter_dsl.tenant_id ≠ JWT tenant |
| RET_004 | `VectorStoreUnavailableError` | 503 | Qdrant unavailable |
| RET_005 | `SparseIndexNotFoundError` | 404 | BM25 index not initialized for tenant |
| RET_006 | `RerankTimeoutError` | 200* | Rerank timeout — returns RRF fallback |
| RET_007 | `CompressionError` | 200* | Compression failed — returns raw content |

*RET_006/007 are soft failures — degraded response, not error HTTP status.

---

## 30. Testing Strategy

### Unit Tests
- `DedupEngine`: SHA-256 exact dedup, Jaccard near-dedup (boundary at 0.92), semantic dedup.
- `FilterDSLCompiler`: tenant enforcement, date range compilation, metadata_eq compilation.
- `ContextCompressor`: sentence relevance scoring, token budget capping, empty input handling.
- `FusionEngine` (extended): configurable k, audit trail output.
- `CrossEncoderReranker`: batch processing, timeout fallback, empty input.

### Integration Tests
- `POST /api/v1/retrieval/search` with FilterDSL (mock Qdrant).
- Cross-tenant filter injection attempt → 403.
- Rerank timeout → fallback to RRF ordering → 200.

### Performance Tests
- P95 of full hybrid pipeline under 400ms for typical query (10 dense + 10 sparse candidates).
- BM25 Redis index load time < 10ms for tenant with 100K chunks.
- Dedup pipeline: 30 candidates processed in < 5ms.

---

## 31. Unit Testing Plan

| Test Class | Tests |
|---|---|
| `TestDedupEngine` | `test_sha256_exact_dedup`, `test_jaccard_near_dedup_boundary`, `test_semantic_dedup_threshold`, `test_empty_input`, `test_all_unique_preserved` |
| `TestFilterDSLCompiler` | `test_tenant_enforcement`, `test_date_range_compilation`, `test_metadata_eq`, `test_cross_tenant_rejected`, `test_null_filter_passthrough` |
| `TestContextCompressor` | `test_sentence_extraction`, `test_token_budget_cap`, `test_compression_ratio_calculation`, `test_empty_content_handling`, `test_min_relevance_threshold` |
| `TestFusionEngineV2` | `test_configurable_k`, `test_audit_trail_output`, `test_rrf_scores_bounded`, `test_single_source_fusion` |
| `TestCrossEncoderRerankerBatched` | `test_batch_processing`, `test_timeout_fallback`, `test_empty_candidate_list`, `test_top_k_bounded` |

---

## 32. Integration Testing Plan

| Test | Description |
|---|---|
| `test_search_with_filterdsl` | End-to-end search with FilterDSL applied |
| `test_search_tenant_isolation` | Two tenants, verify no cross-contamination |
| `test_compress_endpoint` | POST /compress with valid evidence list |
| `test_rerank_timeout_degrades_gracefully` | Inject timeout; verify RRF fallback in response |
| `test_dedup_removes_duplicates` | Insert duplicate chunks; verify dedup count in response |

---

## 33. Performance Testing Plan

| Scenario | Target | Metric |
|---|---|---|
| Full hybrid pipeline (10+10 candidates) | P95 < 400ms | `raguard_retrieval_*_duration_seconds` |
| Dense-only (50 candidates) | P95 < 150ms | OTel span |
| BM25 index Redis load | < 10ms | `raguard_retrieval_sparse_duration_seconds` |
| Dedup pipeline (30 candidates) | < 5ms | OTel span |
| Context compression (10 chunks) | < 50ms | `raguard_retrieval_compression_ratio` |

---

## 34. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| BM25 Redis index memory overflow for large tenants | Medium | High | TTL eviction + async PostgreSQL snapshots |
| Cross-encoder timeout causing P95 > 400ms | Medium | Medium | Hard timeout + RRF fallback (RET_006) |
| FilterDSL complexity explosion from client | Low | Medium | Strict Pydantic model limits depth and fields |
| Semantic dedup false positives remove valid evidence | Low | High | Configurable threshold + disable flag per request |
| Context compression destroys critical context | Low | High | Min relevance threshold + length guard + fallback to raw |

---

## 35. Acceptance Criteria

- [ ] All 5 retrieval stages (Dense, Sparse, RRF, Dedup, Rerank) are individually OTel-instrumented.
- [ ] `FilterDSL` enforces tenant isolation — cross-tenant injection returns 403.
- [ ] Duplicate removal removes all SHA-256 duplicates and Jaccard near-duplicates (threshold 0.92).
- [ ] Context compression achieves ≥20% token reduction on a 10-chunk retrieval result.
- [ ] Cross-encoder timeout (>2000ms) falls back to RRF ordering without error.
- [ ] P95 of full pipeline < 400ms under standard load.
- [ ] All Prometheus metrics listed in §28 are emitted correctly.
- [ ] All unit tests pass with ≥90% coverage on new components.

---

## 36. Completion Criteria

- [ ] All new files created per §19 File Creation Plan.
- [ ] Alembic migration `0009` generated and tested.
- [ ] All unit tests pass (no regressions on existing 328 tests).
- [ ] Integration tests pass.
- [ ] Frontend production build passes.
- [ ] Git commit created.
- [ ] Documentation updated (walkthrough.md + task.md).

---

## 37. Milestone Breakdown

### Milestone 5.1 — FilterDSL & Schema Foundation
**Objective**: Establish the filtering language, DTOs, and compiler.  
**Scope**: New Pydantic models, compiler logic, error taxonomy extension.  
**Components**: `filter_dsl.py`, `filter_dsl_compiler.py`, `errors.py` (RET_006, RET_007).  
**Database Impact**: None.  
**API Changes**: Extend `SearchRequestDTO` with `filter_dsl` field.  
**Testing**: `TestFilterDSLCompiler` (5 tests).  
**Acceptance**: FilterDSL compiles to valid Qdrant filter; tenant enforcement proven by test.

### Milestone 5.2 — Deduplication Engine
**Objective**: Implement production-grade 3-phase deduplication.  
**Scope**: `DedupEngine` with SHA-256, Jaccard, and semantic dedup.  
**Components**: `dedup_engine.py`.  
**Database Impact**: Add `dedup_removed_count` column (migration 0009).  
**Testing**: `TestDedupEngine` (5 tests).  
**Acceptance**: SHA-256 exact dedup removes 100% exact duplicates; Jaccard removes near-duplicates above threshold.

### Milestone 5.3 — BM25 Redis Persistence
**Objective**: Persist BM25 index to Redis with incremental updates.  
**Scope**: Extend `BM25SparseSearchProvider` with Redis persistence.  
**Components**: `providers/sparse/bm25_provider.py` (extended).  
**Database Impact**: None (Redis only).  
**Testing**: `TestSparseRetrievalRedis` (3 tests).  
**Acceptance**: BM25 index survives process restart via Redis; incremental update adds new chunks.

### Milestone 5.4 — Cross-Encoder Batching & Timeout
**Objective**: Harden cross-encoder reranking with batched inference and timeout guard.  
**Scope**: Extend `CohereRerankerProvider` and `LocalRerankerProvider`.  
**Components**: Both reranker providers + base class.  
**Testing**: `TestCrossEncoderRerankerBatched` (5 tests).  
**Acceptance**: Timeout triggers RRF fallback; batch processing handles 30 candidates correctly.

### Milestone 5.5 — Context Compression
**Objective**: Implement TF-IDF-guided context compression.  
**Scope**: `ContextCompressor` service + API endpoint.  
**Components**: `context_compressor.py`, new compress route.  
**Testing**: `TestContextCompressor` (5 tests).  
**Acceptance**: ≥20% token reduction; min_relevance threshold enforced.

### Milestone 5.6 — Orchestrator Integration & Verification
**Objective**: Wire all Phase 5 components into `RetrievalOrchestrator`; run full regression.  
**Scope**: `retrieval_service.py` v2, Alembic migration 0009, API routes v2.  
**Testing**: All new unit tests + integration tests + full 328+ regression suite.  
**Acceptance**: All tests pass; P95 < 400ms confirmed; Git commit ready.

---

## 38. Milestone Dependencies

```
5.1 (FilterDSL Schema) ──► 5.6 (Orchestrator Integration)
5.2 (Dedup Engine)     ──► 5.6
5.3 (BM25 Persistence) ──► 5.6
5.4 (CrossEncoder)     ──► 5.6
5.5 (Compression)      ──► 5.6
```

Milestones 5.1–5.5 can be developed in parallel. 5.6 depends on all prior.

---

## 39. Implementation Checklist

- [ ] Create `backend/modules/retrieval/schemas/filter_dsl.py`
- [ ] Create `backend/modules/retrieval/services/dedup_engine.py`
- [ ] Create `backend/modules/retrieval/services/context_compressor.py`
- [ ] Create `backend/modules/retrieval/services/filter_dsl_compiler.py`
- [ ] Create `backend/modules/retrieval/providers/dense/__init__.py`
- [ ] Create `backend/modules/retrieval/providers/dense/base.py`
- [ ] Create `backend/modules/retrieval/providers/dense/qdrant_provider.py`
- [ ] Modify `backend/modules/retrieval/schemas/retrieval_dto.py` (extend DTOs)
- [ ] Modify `backend/modules/retrieval/schemas/errors.py` (add RET_006, RET_007)
- [ ] Modify `backend/modules/retrieval/services/retrieval_service.py` (wire new components)
- [ ] Modify `backend/modules/retrieval/services/fusion.py` (audit trail + configurable k)
- [ ] Modify `backend/modules/retrieval/providers/sparse/bm25_provider.py` (Redis persistence)
- [ ] Modify reranker providers (batch + timeout)
- [ ] Generate Alembic migration `0009_retrieval_v2_schema.py`
- [ ] Modify `backend/modules/retrieval/api/routes.py` (add compress endpoint; v2 search)
- [ ] Write unit tests (5 new test classes, ~25 tests)
- [ ] Write integration tests (~5 tests)
- [ ] Run full regression suite
- [ ] Run frontend build
- [ ] Update `task.md` and `walkthrough.md`

---

## 40. Deliverables

1. Production-hardened `RetrievalOrchestrator` with FilterDSL, DedupEngine, and ContextCompressor.
2. `FilterDSL` Pydantic model with compiler and tenant enforcement.
3. `DedupEngine` with 3-phase deduplication pipeline.
4. `ContextCompressor` with TF-IDF sentence extraction.
5. Redis-backed BM25 persistence.
6. Cross-encoder batching with timeout fallback.
7. Alembic migration `0009`.
8. Complete unit + integration test suite.
9. Updated Prometheus metrics and Grafana panel definitions.

---

## 41. Documentation Updates Required

- `walkthrough.md`: Phase 5 section.
- `task.md`: Phase 5 milestones.
- `README.md`: Progress tracker update (6/23 stages).
- `docs/ADR/`: ADR-P5-001 (FilterDSL), ADR-P5-002 (Context Compression), ADR-P5-003 (DedupEngine).

---

## 42. Repository Impact

- Files added: ~10 new files.
- Files modified: ~8 existing files.
- Migration: `0009_retrieval_v2_schema.py`.
- Router: No new prefix; existing `/api/v1/retrieval/` extended.
- No breaking changes to existing `RetrievalOrchestrator.execute_hybrid_search()` signature (additive only).

---

## 43. Phase Completion Checklist

- [ ] All milestones 5.1–5.6 completed and verified.
- [ ] Full backend test suite passes (328+ tests).
- [ ] Frontend production build passes.
- [ ] Alembic migration applied and verified.
- [ ] All Prometheus metrics emitting correctly.
- [ ] All OTel spans visible in trace explorer.
- [ ] Git commit: `"Phase 5 Complete: Production-Grade Hybrid Retrieval Engine"`
- [ ] GitHub push to `main`.
- [ ] `task.md` updated (Phase 5 → FROZEN).
- [ ] `walkthrough.md` updated.
- [ ] Progress tracker updated: 6/23 stages (26.1%).
