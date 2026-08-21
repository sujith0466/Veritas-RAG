# Veritas RAG — Phase 2 Milestone 2: Embedding Pipeline
## Document 4: Verification & Freeze Checklist

**Document Version**: 1.0.0
**Milestone**: Phase 2 Milestone 2 (`Embedding Pipeline`)
**Status**: Verification Checklist & Quality Gates

---

## 1. Overview & Gate Philosophy

Before **Phase 2 Milestone 2 (`Embedding Pipeline`)** can be marked as `COMPLETED` and `FROZEN`, the implementation must pass all 12 rigorous multi-layer verification gates listed below. No milestone boundary violations (`NO Qdrant calls`, `NO retrieval operations`, `NO LLM generation`) will be tolerated.

---

## 2. Detailed Review Gates

### Gate 1: Architecture & Boundary Review
- [ ] Verify `backend/modules/embedding/` strictly follows `ADR-005` modular boundaries.
- [ ] **Strict Boundary Audit**: Confirm zero imports of `qdrant_client` or references to Qdrant collection upserts within any file inside `backend/modules/embedding/`.
- [ ] **Strict Boundary Audit**: Confirm zero retrieval, search, or ranking algorithms exist inside the embedding module.
- [ ] Confirm `BaseEmbeddingProvider` interface decouples provider implementation from service logic.

### Gate 2: Security & Tenant Isolation Review
- [ ] Verify all database queries in `EmbeddingRepository` explicitly apply `.where(Entity.tenant_id == tenant_id)`.
- [ ] Verify `POST /api/v1/embeddings/process/{version_id}` enforces `get_current_user` JWT verification and checks tenant access to `version_id`.
- [ ] Verify provider API keys (`OpenAI`, `Cohere`) are never logged in `structlog` or stored in plaintext in `embedding_jobs`.

### Gate 3: Database & Idempotency Review
- [ ] Verify `embedding_jobs` and `chunk_embeddings` tables exist with correct foreign keys (`ON DELETE CASCADE`).
- [ ] Verify unique composite index on `(tenant_id, chunk_id)` and lookup index on `(tenant_id, content_hash)`.
- [ ] **Idempotency Test**: Upload document version $V_1$, generate embeddings ($100$ API calls). Re-trigger embedding on $V_1$ and verify exact $0$ external API calls occur due to `content_hash` cache hit.

### Gate 4: API & Contract Review
- [ ] Verify `/api/v1/embeddings/providers` correctly lists all active providers with exact `dimension` and `model_name`.
- [ ] Verify `/api/v1/embeddings/jobs/{job_id}` returns precise progress rates (`processed_chunks / total_chunks`) and `total_tokens_consumed`.
- [ ] Verify API error responses return structured code envelopes (`EMB_001` through `EMB_005`).

### Gate 5: Celery Worker & Resilience Review
- [ ] Verify `process_embedding_batch_task` executes asynchronously on the `ingestion` queue.
- [ ] **Simulated Rate Limit Audit**: Mock `OpenAI` provider returning `HTTP 429 RateLimitExceeded`. Verify worker catches `EMB_003` and schedules exact exponential backoff (`countdown = 2**retries * 5`).
- [ ] Verify after $7$ failed retries, worker sets `job.status = FAILED`, records `error_message`, and publishes `EmbeddingBatchFailed` event.

### Gate 6: Event Architecture Review
- [ ] Verify `ChunksEmbedded` domain event strictly matches canonical payload schema (`schema_version: "1.0.0"`).
- [ ] Verify `EventDispatcher` successfully emits `ChunksEmbedded` and writes an immutable record into `document_events`.

### Gate 7: Performance & Quota Review
- [ ] Verify embedding requests are batched into chunks of $100$ strings per call (`batch_size=100`).
- [ ] Verify `TokenQuotaValidator` rejects job triggering (`EMB_002`) if tenant token consumption exceeds allocated monthly budget.
- [ ] Verify batch vector insertion into `chunk_embeddings` executes via `bulk_insert_mappings` in $< 150\text{ms}$ for $100$ records.

### Gate 8: Observability & Logging Review
- [ ] Verify Prometheus metrics `raguard_embedding_tokens_total` and `raguard_embedding_latency_seconds` increment accurately.
- [ ] Verify JSON structured logs (`structlog`) emit `job_id`, `tenant_id`, `provider`, `model`, and `tokens_consumed` on every batch completion.

### Gate 9: Frontend Infrastructure UI Review
- [ ] Verify `/embeddings` route is protected by `ProtectedRoute` inside `routes.tsx` and accessible via `Sidebar.tsx`.
- [ ] Verify `EmbeddingJobTable.tsx` displays live progress bars and error tooltips cleanly without UI lag.
- [ ] Verify `ProviderConfigCard.tsx` allows switching active default providers without browser errors.

### Gate 10: Documentation & ADR Review
- [ ] Confirm `ADR-M2-001` (Decoupled Vector Generation) and `ADR-M2-002` (Dynamic Batching & Backoff) are documented.
- [ ] Confirm API endpoints and schemas are auto-documented in `/docs` (FastAPI OpenAPI spec).

### Gate 11: Regression Review across Previous Milestones
- [ ] Run full test suite covering `Phase 1 (M1–M6)` and `Phase 2 Milestone 1 (Chunking)`.
- [ ] Verify $100\%$ pass rate across all previous tests ($158+$ tests passing).

### Gate 12: Architecture Sign-Off & Freeze Sign-Off
- [ ] Principal Software Architect sign-off: `APPROVED`
- [ ] AI Infrastructure Lead sign-off: `APPROVED`
- [ ] Security Architect sign-off: `APPROVED`

---

## 3. Milestone Freeze Confirmation

Once all 12 gates above are checked `[x]`, the following freeze declaration becomes official:

> **MILESTONE 2 FREEZE DECLARATION**
> `Phase 2 Milestone 2: Embedding Pipeline` is officially **VERIFIED and FROZEN**. No further modifications to `backend/modules/embedding/` or `chunk_embeddings` schemas are permitted unless a critical defect is identified. Development may now advance to `Phase 2 Milestone 3: Vector Storage Foundation`.
