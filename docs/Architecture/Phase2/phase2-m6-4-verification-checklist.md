# Veritas RAG — Phase 2 Milestone 6: Knowledge Health & Lifecycle Management
## Document 4: Verification & Freeze Checklist

**Document Version**: 1.0.0
**Milestone**: Phase 2 Milestone 6 (`Knowledge Health & Lifecycle Management`)
**Status**: Verification Checklist & Quality Gates

---

## 1. Overview & Gate Philosophy

Before **Phase 2 Milestone 6 (`Knowledge Health & Lifecycle Management`)** and the **entire Phase 2 (`Knowledge Layer & Retrieval Foundation`)** can be marked as `COMPLETED` and `FROZEN`, the implementation must pass all 12 rigorous multi-layer verification gates listed below. No milestone boundary violations (`NO analytics dashboards`, `NO evaluation benchmarks`) will be tolerated.

---

## 2. Detailed Review Gates

### Gate 1: Architecture & Boundary Review
- [ ] Verify `backend/modules/knowledge_health/` strictly follows `ADR-005` modular boundaries.
- [ ] **Strict Boundary Audit**: Confirm zero imports of analytics charting engines or RAG Triad evaluation metrics (`Context Relevance, Groundedness`) within `backend/modules/knowledge_health/`.
- [ ] **Strict Boundary Audit**: Confirm zero retrieval execution or generation logic exists inside the health module (`only audit, parity check, and purge allowed`).
- [ ] Confirm `PurgeOrchestrator` and `OrphanCleanupEngine` cleanly decouple database row sweeps from Qdrant vector deletion wrappers.

### Gate 2: Security & Tenant Isolation Review
- [ ] Verify `PurgeOrchestrator.execute_two_phase_purge()` and all REST endpoints require JWT RS256 verification (`get_current_user`) and strictly verify `Role.ADMIN` or `Role.OWNER` authorization before deleting data.
- [ ] Verify `OrphanCleanupEngine` and `IntegrityAuditor` strictly isolate all sweeps and scans using `.where(Entity.tenant_id == tenant_id)`.

### Gate 3: Two-Phase Purge Synchronization Review
- [ ] Verify `PurgeOrchestrator` implements two-phase deletion (`ADR-M6-001`).
- [ ] **Simulated Crash Test**: Mark document $D_1$ as `DELETED`. Simulate network crash before Qdrant deletion completes. Run scheduled `OrphanCleanupEngine` sweep. Verify the sweep catches $D_1$, successfully purges Qdrant points, and removes database rows cleanly without leaving phantom vectors.

### Gate 4: Integrity Auditor & Parity Review
- [ ] Verify `IntegrityAuditor.verify_tenant_parity(tenant_id)` returns `parity_status = SYNCED` when `DocumentChunk` ($is\_embedded=True$) exact count equals Qdrant collection point count.
- [ ] **Mismatch Detection Test**: Manually delete $5$ points from Qdrant directly via API. Run `verify_tenant_parity()`. Verify auditor returns `MISMATCH_DETECTED` and triggers automatic reconciliation task.

### Gate 5: Model Rotation & Shadow Migration Review
- [ ] Verify `StaleEmbeddingScanner` detects when active tenant provider configuration changes (`ADR-M6-002`).
- [ ] **Shadow Rotation Test**: Trigger model rotation from `OpenAI 1536-dim` to `Cohere 1024-dim`. Verify shadow collection is created, populated asynchronously, and swapped with zero dropped queries on active search traffic.

### Gate 6: Event Architecture Review
- [ ] Verify `OrphanChunksPurged` and `KnowledgeDriftDetected` domain events strictly match canonical payload schemas (`schema_version: "1.0.0"`).
- [ ] Verify `EventDispatcher` successfully emits `OrphanChunksPurged` whenever scheduled sweeps or hard purges complete.

### Gate 7: Performance & Streaming Sweep Review
- [ ] **Sweep Benchmark**: Execute `sweep_orphaned_chunks()` against a database containing $1,000,000$ chunk rows. Verify the scanner uses SQL cursor streaming and completes in $\le 4.5\text{ seconds}$ with zero memory spikes (`OOM prevention`).
- [ ] Verify Qdrant vector deletions execute via non-blocking `delete_points_by_filter()` commands in $< 50\text{ms}$.

### Gate 8: Observability & Logging Review
- [ ] Verify Prometheus metrics `raguard_knowledge_parity_mismatches_total` and `raguard_orphans_purged_total` increment accurately across scans.
- [ ] Verify JSON structured logs (`structlog`) emit `scan_type`, `orphans_purged`, `parity_status`, and `duration_ms` on every scan completion.

### Gate 9: Frontend Health Console UI Review
- [ ] Verify `/knowledge-health` route is protected inside `routes.tsx` and accessible via `Sidebar.tsx`.
- [ ] Verify `ParityAuditCard.tsx` displays real-time `SYNCED` vs `MISMATCH` badges clearly.
- [ ] Verify `ModelRotationModal.tsx` guides administrators safely through shadow migrations without browser errors.

### Gate 10: Documentation & ADR Review
- [ ] Confirm `ADR-M6-001` (Two-Phase Purge Synchronization) and `ADR-M6-002` (Shadow Collection Model Rotation) are documented.
- [ ] Confirm API endpoints and schemas are auto-documented in `/docs` (FastAPI OpenAPI spec).

### Gate 11: Regression Review across ALL Phase 1 & Phase 2 Milestones
- [ ] Run complete master test suite covering `Phase 1 (M1–M6)`, `Phase 2 M1 (Chunking)`, `Phase 2 M2 (Embeddings)`, `Phase 2 M3 (Vector Storage)`, `Phase 2 M4 (Hybrid Retrieval)`, and `Phase 2 M5 (Reliability)`.
- [ ] Verify $100\%$ pass rate across all tests across the entire platform ($158+$ tests passing).

### Gate 12: Master Architecture Sign-Off & Phase 2 Freeze Sign-Off
- [ ] Principal Data Platform Architect sign-off: `APPROVED`
- [ ] AI Infrastructure Lead sign-off: `APPROVED`
- [ ] Security Architect sign-off: `APPROVED`

---

## 3. Milestone & Phase 2 Freeze Confirmation

Once all 12 gates above are checked `[x]`, the following freeze declaration becomes official:

> **MILESTONE 6 & PHASE 2 MASTER FREEZE DECLARATION**
> `Phase 2 Milestone 6: Knowledge Health & Lifecycle Management` and the complete **`Phase 2: Knowledge Layer & Retrieval Foundation` (`Milestones 1 through 6`)** are officially **VERIFIED and FROZEN**. No further modifications to Phase 2 modules (`chunking, embedding, vector, retrieval, reliability, knowledge_health`) are permitted unless a critical defect is identified. Development may now advance to **`Phase 3: Confidence, Evaluation & Self-Correction Engine`**.
