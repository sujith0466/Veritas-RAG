# RAGuard AI — Phase 2 Milestone 4: Hybrid Retrieval Engine
## Document 4: Verification & Freeze Checklist

**Document Version**: 1.0.0
**Milestone**: Phase 2 Milestone 4 (`Hybrid Retrieval Engine`)
**Status**: Verification Checklist & Quality Gates

---

## 1. Overview & Gate Philosophy

Before **Phase 2 Milestone 4 (`Hybrid Retrieval Engine`)** can be marked as `COMPLETED` and `FROZEN`, the implementation must pass all 12 rigorous multi-layer verification gates listed below. No milestone boundary violations (`NO self-correction`, `NO query rewrite`, `NO answer generation`) will be tolerated.

---

## 2. Detailed Review Gates

### Gate 1: Architecture & Boundary Review
- [ ] Verify `backend/modules/retrieval/` strictly follows `ADR-005` modular boundaries.
- [ ] **Strict Boundary Audit**: Confirm zero imports of LLM chat completion/generation clients (`openai.chat.completions`, `cohere.generate`) within `backend/modules/retrieval/`.
- [ ] **Strict Boundary Audit**: Confirm zero circuit breakers or degraded-mode routing logic exist (`reserved for Milestone 5`).
- [ ] Confirm `BaseSparseSearchProvider` and `BaseRerankerProvider` cleanly decouple algorithms from domain orchestration.

### Gate 2: Security & Tenant Isolation Review
- [ ] Verify `RetrievalOrchestrator.execute_hybrid_search()` enforces that every query passed into `Qdrant` and `BM25` injects `tenant_id`.
- [ ] Verify REST endpoints (`POST /api/v1/retrieval/search`) require JWT RS256 verification (`get_current_user`) and sanitize input query length ($\le 2,000$ characters).
- [ ] Verify `retrieval_queries` audit entries isolate records via `.where(RetrievalQueryLog.tenant_id == tenant_id)`.

### Gate 3: RRF & Near-Duplicate Deduplication Review
- [ ] Verify `FusionEngine.execute_rrf_fusion` strictly applies RRF formula with $k=60$ (`ADR-M4-001`).
- [ ] **Deduplication Test**: Inject 3 identical `chunk_id` items across dense and sparse lists plus 2 near-duplicate strings (`Jaccard = 0.95`). Verify `deduplicate_candidates()` returns exact $1$ unique surviving candidate before passing to the reranker (`ADR-M4-002`).

### Gate 4: Concurrency & Multi-Stage Execution Review
- [ ] Verify `embed_query` + `Qdrant dense search` and `BM25 sparse search` execute concurrently via `await asyncio.gather()`.
- [ ] Verify `Cross-Encoder Reranker` input is strictly capped to $top\_n = 30$ candidates (`never reranking all 100 raw candidates`).
- [ ] Verify stage latency breakdown timers (`dense_ms`, `sparse_ms`, `rrf_ms`, `rerank_ms`) equal or approximate `total_duration_ms`.

### Gate 5: Database Audit Log Review
- [ ] Verify `retrieval_queries` table exists with correct `JSONB` stage breakdown schema and composite indexes `(tenant_id, created_at)`.
- [ ] Verify asynchronous query execution logging does not add blocking latency to synchronous `execute_hybrid_search()` responses.

### Gate 6: Event Architecture Review
- [ ] Verify `QueryRetrieved` domain event strictly matches canonical payload schema (`schema_version: "1.0.0"`).
- [ ] Verify `EventDispatcher` successfully emits `QueryRetrieved` and writes an immutable record into `document_events`.

### Gate 7: Performance & Latency SLA Review
- [ ] **SLA Benchmark**: Execute $1,000$ hybrid search queries against an index of $50,000$ points. Verify $P_{95}$ total execution latency completes in $\le 380\text{ms}$.
- [ ] Verify `BM25SparseSearchProvider` LRU tenant memory cache evicts cleanly when `max_tenants=500` threshold is reached without memory leaks.

### Gate 8: Observability & Logging Review
- [ ] Verify Prometheus metrics `raguard_retrieval_queries_total` and `raguard_retrieval_latency_seconds` increment accurately across stages.
- [ ] Verify JSON structured logs (`structlog`) emit `correlation_id`, `query_length`, `top_k`, and `stage_breakdown_json` on every search completion.

### Gate 9: Frontend Search Sandbox UI Review
- [ ] Verify `/retrieval` route is protected inside `routes.tsx` and accessible via `Sidebar.tsx`.
- [ ] Verify `SearchSandbox.tsx` displays all 4 columns (`Dense`, `Sparse`, `RRF`, `Reranked`) side-by-side with clear score differentials.
- [ ] Verify `EvidenceCard.tsx` renders section breadcrumbs and highlighted match badges accurately without layout shifts.

### Gate 10: Documentation & ADR Review
- [ ] Confirm `ADR-M4-001` (Reciprocal Rank Fusion $k=60$) and `ADR-M4-002` (Two-Stage Deduplication & Reranking Bounds) are documented.
- [ ] Confirm API endpoints and schemas are auto-documented in `/docs` (FastAPI OpenAPI spec).

### Gate 11: Regression Review across Previous Milestones
- [ ] Run full test suite covering `Phase 1 (M1–M6)`, `Phase 2 M1 (Chunking)`, `Phase 2 M2 (Embeddings)`, and `Phase 2 M3 (Vector Storage)`.
- [ ] Verify $100\%$ pass rate across all previous tests ($158+$ tests passing).

### Gate 12: Architecture Sign-Off & Freeze Sign-Off
- [ ] Principal AI Search Scientist sign-off: `APPROVED`
- [ ] AI Infrastructure Lead sign-off: `APPROVED`
- [ ] Security Architect sign-off: `APPROVED`

---

## 3. Milestone Freeze Confirmation

Once all 12 gates above are checked `[x]`, the following freeze declaration becomes official:

> **MILESTONE 4 FREEZE DECLARATION**
> `Phase 2 Milestone 4: Hybrid Retrieval Engine` is officially **VERIFIED and FROZEN**. No further modifications to `backend/modules/retrieval/` or `retrieval_queries` schemas are permitted unless a critical defect is identified. Development may now advance to `Phase 2 Milestone 5: Retrieval Reliability Framework`.
