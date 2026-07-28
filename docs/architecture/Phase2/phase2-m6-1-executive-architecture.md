# RAGuard AI — Phase 2 Milestone 6: Knowledge Health & Lifecycle Management
## Document 1: Executive Architecture

**Document Version**: 1.0.0  
**Milestone**: Phase 2 Milestone 6 (`Knowledge Health & Lifecycle Management`)  
**Status**: Architectural Blueprint (Strict Planning Only — No Code)  
**Author**: Principal Data Platform Architect & AI Infrastructure Engineering Team  

---

## 1. Executive Summary

The **Phase 2 Milestone 6: Knowledge Health & Lifecycle Management** establishes the automated governance, garbage collection, and synchronization maintenance infrastructure responsible for preserving absolute consistency across PostgreSQL document chunks (`M1`), dense embeddings (`M2`), Qdrant vector points (`M3`), and keyword indexes (`M4`).

Operating within `backend/modules/knowledge_health/` under strict **Domain-Oriented Modular Architecture (`ADR-005`)**, this module ensures that as documents are updated, deleted, or re-vectorized over time, the underlying knowledge store remains clean, drift-free, and perfectly synchronized. It implements asynchronous orphan cleanup jobs, stale embedding detectors triggered upon model rotation, semantic drift audit scans, and two-phase hard/soft purge orchestration across all storage layers.

---

## 2. Business Goal & Purpose

In long-running enterprise RAG systems, the knowledge base inevitably suffers from entropy and synchronization decay:
1. **Orphaned Vector Pollution**: When a user deletes a document version from PostgreSQL, residual vectors left behind in Qdrant continue surfacing in retrieval results (`phantom hallucination`).
2. **Model Rotation Bloat**: Switching a tenant's embedding provider from `OpenAI` (`1536-dim`) to `Cohere` (`1024-dim`) without systematically identifying and re-vectorizing stale chunks breaks vector space geometry.
3. **Storage & Cost Bloat**: Without scheduled garbage collection, stale `chunk_embeddings` and inactive Qdrant payloads accumulate indefinitely, inflating cloud hosting and RAM footprint costs.

The **Knowledge Health Engine** solves these challenges by automating asynchronous audit and repair sweeps (`HealthScanJob`), guaranteeing $100\%$ transactional consistency across PostgreSQL and Qdrant (`ADR-M6-001`).

---

## 3. Scope & Objectives

### In Scope
- **Two-Phase Purge Orchestrator (`PurgeOrchestrator`)** synchronizing soft and hard deletions across `documents`, `document_versions`, `document_chunks`, `chunk_embeddings`, and `Qdrant` vector points.
- **Orphan Chunk Cleanup Worker (`OrphanCleanupEngine`)** periodically auditing and sweeping unreferenced chunks or vector points lacking valid parent documents (`ADR-M6-001`).
- **Stale Embedding Detector (`StaleEmbeddingScanner`)** identifying chunks whose `(provider, model_name)` no longer match the tenant's active configuration and automatically enqueueing batch re-embedding jobs (`M2`).
- **Vector Drift & Integrity Auditor (`IntegrityScanner`)** executing scheduled consistency checks verifying $1:1$ count parity between PostgreSQL `DocumentChunk` records and Qdrant collection points.
- REST API endpoints (`/api/v1/knowledge-health/*`) for triggering audit scans, viewing stale embedding reports, launching re-index campaigns, and executing manual purges.
- Frontend Infrastructure UI (`/knowledge-health`) providing an administrative Health Console displaying parity badges, orphan counts, and model rotation progress bars.

### Out of Scope (Strict Boundaries)
- **NO Analytics Dashboards**: No general usage analytics, user query heatmaps, or billing metrics (`reserved for Phase 4`).
- **NO Evaluation Benchmarks**: No RAG Triad evaluation (`Context Relevance, Groundedness, Answer Relevance`) or retrieval scoring accuracy benchmarks (`reserved for Phase 4`).
- **NO Production Monitoring beyond Lifecycle**: No general APM, CPU/RAM container metrics, or HTTP router monitoring (`handled by Phase 1 M5 / Grafana`).
- **NO Retrieval or Generation Mechanics**: No search execution, fusion, or LLM generation.

---

## 4. Deliverables

1. **Executive Architecture** (`this document`): High-level strategy, two-phase purge workflows, and boundaries.
2. **Technical Design (`phase2_m6_2_technical_design.md`)**: Complete DORA structure, Mermaid sequence/class diagrams, audit state models (`health_scan_jobs`, `stale_embedding_records`), REST APIs, Celery periodic workers, security, and performance (`batched scanning`).
3. **Implementation Roadmap (`phase2_m6_3_roadmap.md`)**: Phased execution plan from orphan scanners through API/UI health console integration.
4. **Verification & Freeze Checklist (`phase2_m6_4_verification_checklist.md`)**: Strict multi-layer audit gates required prior to freezing Milestone 6 and completing Phase 2.

---

## 5. Architectural Boundaries & Dependencies

```mermaid
graph TD
    subgraph Phase 1 & Phase 2 M1–M3 Storage Tiers
        PG_DOC[PostgreSQL Documents / Versions]
        PG_CHK[PostgreSQL DocumentChunk M1]
        PG_EMB[PostgreSQL ChunkEmbedding M2]
        QD_VEC[Qdrant Vector Cluster M3]
    end

    subgraph Milestone 6: Knowledge Health & Lifecycle
        M6[Knowledge Health Orchestrator]
        M6 -->|Audit & Sweep Orphans| PG_CHK
        M6 -->|Audit & Sweep Orphans| PG_EMB
        M6 -->|Delete Points by Filter| QD_VEC
        M6 -->|Detect Stale Models| STALE[StaleEmbeddingScanner]
        STALE -->|Enqueue Re-Embedding| M2_WORKER[Embedding Celery Worker M2]
        M6 -->|Log Scan History| H_DB[(health_scan_jobs Table)]
        M6 -->|Emits Versioned Event| EV[OrphanChunksPurged Event]
    end
```

### Previous Dependencies (`Prerequisites`)
- `DocumentChunk` and `chunk_embeddings` tables in PostgreSQL (`Phase 2 M1 & M2`).
- `QdrantVectorDBProvider.delete_points_by_filter()` (`Phase 2 Milestone 3`).
- `EmbeddingService.trigger_document_embedding()` (`Phase 2 Milestone 2`).
- Celery periodic worker (`Celery Beat`) infrastructure (`Phase 1 Milestone 5`).

### Future Dependencies (`Enables`)
- **Phase 3 & Phase 4**: Guarantees that all evaluation engines and confidence checks operate over a mathematically clean, drift-free vector index.

---

## 6. Architecture Decisions (`ADR-Style Rationale`)

### ADR-M6-001: Two-Phase Transactional Purge Synchronization
- **Context**: Deleting a document from PostgreSQL (`documents table`) inside a database transaction does not automatically delete corresponding vector points from external Qdrant over network boundaries.
- **Decision**: All document deletions must execute through a **Two-Phase Purge Orchestrator**:
  - **Phase 1 (Mark Soft-Deleted)**: PostgreSQL records (`documents`, `document_versions`) are updated with `deleted_at = NOW()` and `status = DELETED`.
  - **Phase 2 (Async Hard Purge)**: A Celery worker (`knowledge_health.execute_hard_purge_task`) calls `QdrantVectorDBProvider.delete_points_by_filter(document_id)` first. Only upon confirmed Qdrant deletion acknowledgment does the worker execute `DELETE FROM documents WHERE id = document_id` in PostgreSQL.
- **Rationale**: Prevents orphaned Qdrant vectors (`phantom evidence`) if the network drops midway through deletion. If Phase 2 fails, the scheduled `OrphanCleanupEngine` catches marked `DELETED` records and retries Qdrant purging until clean.

### ADR-M6-002: Model Rotation Re-Indexing via Shadow Collections
- **Context**: When a tenant rotates their default embedding model (e.g., `OpenAI 1536-dim` $\rightarrow$ `Cohere 1024-dim`), we cannot simply overwrite vectors in the live Qdrant collection without taking the tenant's search offline.
- **Decision**: Model rotation must execute via **Shadow Collection Migration**:
  1. `StaleEmbeddingScanner` detects the config change and creates a new shadow Qdrant collection (`raguard_knowledge_cohere_1024`).
  2. Batch re-embedding jobs populate the shadow collection asynchronously (`M2 & M3`).
  3. Once parity is verified ($100\%$ point count), `TenantCollectionConfig` swaps pointer to the new collection atomically (`0ms downtime`), and the old collection/embeddings are scheduled for cleanup after a 7-day retention grace period.

---

## 7. Success Criteria

- **Parity Fidelity**: $100\%$ exact match between active `DocumentChunk` count in PostgreSQL and active point count across Qdrant collections after scheduled health sweeps.
- **Zero Orphan Leakage**: $0$ orphaned vector points remain in Qdrant $24\text{ hours}$ after a parent document version is marked `DELETED`.
- **Zero-Downtime Model Rotation**: Tenant embedding provider migration completes with zero dropped search queries during transition.
