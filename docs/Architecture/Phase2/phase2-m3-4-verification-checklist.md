# Veritas RAG — Phase 2 Milestone 3: Vector Storage Foundation
## Document 4: Verification & Freeze Checklist

**Document Version**: 1.0.0
**Milestone**: Phase 2 Milestone 3 (`Vector Storage Foundation`)
**Status**: Verification Checklist & Quality Gates

---

## 1. Overview & Gate Philosophy

Before **Phase 2 Milestone 3 (`Vector Storage Foundation`)** can be marked as `COMPLETED` and `FROZEN`, the implementation must pass all 12 rigorous multi-layer verification gates listed below. No milestone boundary violations (`NO similarity search`, `NO reranking`, `NO embedding generation`) will be tolerated.

---

## 2. Detailed Review Gates

### Gate 1: Architecture & Boundary Review
- [ ] Verify `backend/modules/vector/` strictly follows `ADR-005` modular boundaries.
- [ ] **Strict Boundary Audit**: Confirm zero imports of embedding generation clients (`openai.embeddings`, `cohere`) inside any file within `backend/modules/vector/`.
- [ ] **Strict Boundary Audit**: Confirm zero search queries (`client.search()` or `ANN similarity algorithms`) exist within the vector storage foundation (`only upsert, delete, ensure_collection`).
- [ ] Confirm `BaseVectorDBProvider` interface decouples vector database mechanics from domain services.

### Gate 2: Security & Tenant Isolation Review
- [ ] Verify `QdrantVectorDBProvider.upsert_points()` enforces that every point payload contains `tenant_id`.
- [ ] Verify `delete_points_by_filter()` strictly applies `Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))])` to prevent cross-tenant deletion.
- [ ] Verify REST endpoints require JWT RS256 verification (`get_current_user`) and administrative authorization for collection dropping (`Role.ADMIN`).

### Gate 3: Qdrant Collection Topology & Payload Index Review
- [ ] Verify `ensure_collection()` configures HNSW indexes with `ScalarQuantizationConfig(type=ScalarType.INT8)` (`75% RAM reduction`).
- [ ] Verify Qdrant payload keyword indexes (`create_payload_index`) are verified/created for `tenant_id`, `document_id`, `document_version_id`, `content_hash`, and `strategy_used`.

### Gate 4: Database & Sync State Review
- [ ] Verify `vector_index_metadata` table exists with correct foreign keys (`ON DELETE CASCADE`).
- [ ] Verify unique composite constraint on `(tenant_id, document_version_id)` prevents duplicate sync progress entries.
- [ ] **Consistency Test**: Synchronize document version $V_1$ ($100$ chunks). Verify `vector_index_metadata.point_count == 100` and query Qdrant directly to confirm exact $100$ points exist for that `document_version_id`.

### Gate 5: Celery Worker & Resilience Review
- [ ] Verify `sync_vectors_to_qdrant_task` executes asynchronously on the `ingestion` queue.
- [ ] **Simulated Connection Drop Audit**: Stop Qdrant Docker container during active batch indexing. Verify worker catches `VEC_003` and schedules exact exponential backoff (`countdown = 2**retries * 5`).
- [ ] Verify upon Qdrant container restart, worker resumes and completes upsert cleanly (`idempotent overwrite`).

### Gate 6: Event Architecture Review
- [ ] Verify `VectorsIndexed` domain event strictly matches canonical payload schema (`schema_version: "1.0.0"`).
- [ ] Verify `EventDispatcher` successfully emits `VectorsIndexed` and writes an immutable record into `document_events`.

### Gate 7: Performance & gRPC Batching Review
- [ ] Verify vector point upserts execute via `gRPC` (`prefer_grpc=True`) in batches of $500$ points (`batch_size=500`).
- [ ] Verify sustained indexing throughput reaches $\ge 4,000$ points/second on local testing environment without CPU/RAM throttling.

### Gate 8: Observability & Logging Review
- [ ] Verify Prometheus metrics `raguard_vector_points_total` and `raguard_vector_upsert_latency_seconds` increment accurately.
- [ ] Verify JSON structured logs (`structlog`) emit `collection_name`, `points_upserted`, `duration_ms`, and `tenant_id` on every sync completion.

### Gate 9: Frontend Infrastructure UI Review
- [ ] Verify `/vectors` route is protected inside `routes.tsx` and accessible via `Sidebar.tsx`.
- [ ] Verify `CollectionHealthCard.tsx` displays live Qdrant collection statistics cleanly.
- [ ] Verify `IndexSyncTable.tsx` allows triggering manual `Resync` for failed document synchronizations without errors.

### Gate 10: Documentation & ADR Review
- [ ] Confirm `ADR-M3-001` (Collection-per-Domain + Payload Filtering) and `ADR-M3-002` (gRPC Batching & Pooling) are documented.
- [ ] Confirm API endpoints and schemas are auto-documented in `/docs` (FastAPI OpenAPI spec).

### Gate 11: Regression Review across Previous Milestones
- [ ] Run full test suite covering `Phase 1 (M1–M6)`, `Phase 2 M1 (Chunking)`, and `Phase 2 M2 (Embeddings)`.
- [ ] Verify $100\%$ pass rate across all previous tests ($158+$ tests passing).

### Gate 12: Architecture Sign-Off & Freeze Sign-Off
- [ ] Principal Database Architect sign-off: `APPROVED`
- [ ] AI Infrastructure Lead sign-off: `APPROVED`
- [ ] Security Architect sign-off: `APPROVED`

---

## 3. Milestone Freeze Confirmation

Once all 12 gates above are checked `[x]`, the following freeze declaration becomes official:

> **MILESTONE 3 FREEZE DECLARATION**
> `Phase 2 Milestone 3: Vector Storage Foundation` is officially **VERIFIED and FROZEN**. No further modifications to `backend/modules/vector/` or `vector_index_metadata` schemas are permitted unless a critical defect is identified. Development may now advance to `Phase 2 Milestone 4: Hybrid Retrieval Engine`.
