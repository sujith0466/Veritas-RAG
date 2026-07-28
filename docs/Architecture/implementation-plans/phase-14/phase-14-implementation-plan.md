# Phase 14 Implementation Plan — Knowledge Health & Automated Cleanup Engine (Production Grade)

**Phase Name:** Phase 14 — Knowledge Health & Automated Cleanup Engine  
**Target Module:** `backend/modules/knowledge_health/`  
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)  
**Author:** RAGuard Principal Architecture & Enterprise QA Team  

---

## 1. Executive Summary

Phase 14 delivers the enterprise **Knowledge Health & Automated Cleanup Engine** (`backend/modules/knowledge_health/`), establishing continuous self-healing, automated background sweeps, and comprehensive vector-DB/relational-DB synchronization. Extending the Phase 3 baseline (`KnowledgeHealthOrchestrator`, `IntegrityAuditor`, `StaleEmbeddingScanner`, `PurgeOrchestrator`), Phase 14 introduces autonomous scheduled workers (`OrphanCleanupWorker`, `ParityRepairWorker`), dead-letter quarantine (`QuarantineEngine`), and real-time composite health indexing (`KnowledgeHealthScoreEngine`). All background tasks run via Celery/asyncio workers with distributed locking (`RedisLock`), ensuring zero-downtime maintenance and immutable audit logging (`alembic` migration `0015`).

---

## 2. Phase Objectives

1. **Automated Background Workers**: Schedule autonomous sweeps (`OrphanCleanupWorker`, `ParityRepairWorker`, `StaleEmbeddingScannerWorker`) to run without manual API triggers.
2. **Self-Healing Parity Repair**: Automatically resolve 1:1 count discrepancies between PostgreSQL document records and Qdrant vector points.
3. **Quarantine & Dead-Letter Storage**: Isolate corrupted or malformed vector chunks into a dedicated quarantine table (`quarantine_chunks`) instead of dropping data silently.
4. **Knowledge Health Indexing**: Calculate real-time composite health scores (`KnowledgeHealthIndexDTO`) across parity, freshness, and orphan ratios.
5. **Observability & REST APIs**: Provide operational management endpoints (`/api/v1/health/*`) and emit structured background scan events.

---

## 3. Business Goals

* **Zero Vector Storage Drift**: Ensure 100% parity between relational metadata and vector database points over multi-year continuous operations.
* **Storage Cost Optimization**: Automatically reclaim unused Qdrant memory/disk space by purging orphaned vectors and stale embeddings.
* **Autonomous Maintenance**: Eliminate manual engineering intervention required for periodic database cleanups and re-indexing campaigns.

---

## 4. Technical Goals

* **Extend Existing Orchestrator**: Build upon `backend/modules/knowledge_health/services/health_service.py` by adding automated scheduled runners and self-healing repair routines while keeping manual scan APIs intact.
* **Distributed Concurrency Locking**: Enforce Redis-based distributed locks (`redis_lock.acquire("raguard:health:orphan_sweep")`) so multi-replica deployments never execute overlapping background purges.
* **SLA-Bounded Workers**: Rate-limit background deletion batches (`batch_size=500`, `sleep_ms=10`) to prevent high-throughput purges from degrading production retrieval latency.

---

## 5. Scope

* Extension of `KnowledgeHealthOrchestrator` (`services/health_service.py`).
* Implementation of scheduled workers (`workers/orphan_worker.py`, `workers/parity_worker.py`, `workers/stale_worker.py`).
* Implementation of `KnowledgeHealthScoreEngine` (`services/health_scorer.py`).
* Implementation of `QuarantineEngine` (`cleanups/quarantine.py`).
* REST API endpoints (`POST /api/v1/health/scan/schedule`, `GET /api/v1/health/index/{tenant_id}`, `GET /api/v1/health/quarantine`).
* Database migration `alembic/versions/0015_knowledge_health_automation.py` creating `quarantine_chunks` and adding health index columns.

---

## 6. Out of Scope

* Initial document ingestion and chunking (governed by Phase 1).
* Vector similarity search and reranking (governed by Phase 5).
* Real-time generation reliability scoring (governed by Phase 13).

---

## 7. PRD Alignment

Aligns directly with PRD Section 5.3 (*Knowledge Base Integrity, Synchronization, and Self-Healing*), mandating autonomous background repair of vector storage anomalies.

---

## 8. Architecture Alignment

Strictly adheres to `ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `DATABASE_DESIGN_AFTER_IMPROVEMENTS.md`. It acts as the background storage governor ensuring high-fidelity retrieval indices for Phase 5.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 1 (`ingestion`, `chunking`, `vector`): Consumes document metadata and vector points.
  * Phase 3 (`knowledge_health` baseline): Consumes `IntegrityAuditor` and `OrphanCleanupEngine`.
* **Downstream Dependencies**:
  * Phase 5 (`retrieval`): Relies on clean, un-corrupted indices to maintain retrieval precision.
  * Phase 16 (`dashboard`): Visualizes real-time `KnowledgeHealthIndexDTO` across tenants.

---

## 10. Existing Codebase Review

* `backend/modules/knowledge_health/services/health_service.py`: Contains `KnowledgeHealthOrchestrator.run_health_scan()` executing on-demand scans.
* `backend/modules/knowledge_health/Audits/integrity.py`: Contains `IntegrityAuditor.verify_tenant_parity()`.
* `backend/modules/knowledge_health/cleanups/orphans.py`: Contains `OrphanCleanupEngine.sweep_orphaned_chunks()`.
* **Justification for New Components**: Existing engines only run synchronously on demand. Phase 14 requires scheduled workers, automatic parity repair loops, and quarantine tables.

---

## 11. High-Level Architecture

```
Scheduled Cron / Celery Worker
            │
            ▼ (Distributed Redis Lock)
┌────────────────────────────────────────────────────────┐
│ AutomatedHealthScheduler (Phase 14 Orchestrator)      │
│  ├─► OrphanCleanupWorker ──► OrphanCleanupEngine      │
│  ├─► ParityRepairWorker ───► IntegrityAuditor + Repair│
│  └─► StaleScannerWorker ───► StaleEmbeddingScanner    │
└────────────────────────────────────────────────────────┘
            │
            ▼ (Quarantine Engine & Score Engine)
Quarantine Table (`quarantine_chunks`) + `KnowledgeHealthIndexDTO`
```

---

## 12. Low-Level Design

### Self-Healing Parity Repair
When `IntegrityAuditor` detects `qdrant_count != postgres_count`:
1. Query missing chunk IDs: $D_{\text{missing}} = \{c_{\text{pg}} \notin C_{\text{qdrant}}\}$.
2. Query orphaned points: $D_{\text{orphan}} = \{c_{\text{qdrant}} \notin C_{\text{pg}}\}$.
3. For $D_{\text{orphan}}$, execute `vector_service.delete_by_ids()`.
4. For $D_{\text{missing}}$, re-enqueue document chunks into the background ingestion queue (`reindex_queue`) with high priority.

### Knowledge Health Index ($H_{\text{index}}$)
Formula ($0.0 - 100.0$):
$$H_{\text{index}} = 100.0 \times \left( 0.50 \cdot P_{\text{ratio}} + 0.30 \cdot (1 - O_{\text{ratio}}) + 0.20 \cdot F_{\text{ratio}} \right)$$
Where $P_{\text{ratio}}$ is parity match ($1.0$ if parity, else $1 - \frac{|\Delta|}{N}$), $O_{\text{ratio}}$ is orphan fraction, and $F_{\text{ratio}}$ is fresh embedding fraction.

---

## 13. Component Design

1. **`AutomatedHealthScheduler`**: Coordinates cron triggers and checks Redis locks.
2. **`ParityRepairWorker`**: Executes self-healing synchronization loops.
3. **`QuarantineEngine`**: Moves malformed chunks (`corrupted_payload`, `missing_vector`) to PostgreSQL quarantine instead of permanent drop.
4. **`KnowledgeHealthScoreEngine`**: Computes and caches tenant health indexes.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/health_dto.py` | Add `KnowledgeHealthIndexDTO`, `QuarantineChunkDTO`, `ParityRepairResultDTO`. |
| `workers/orphan_worker.py` | Background scheduled task executing orphan sweeps with batch throttling. |
| `workers/parity_worker.py` | Background scheduled task detecting and repairing count mismatches. |
| `cleanups/quarantine.py` | Quarantine engine storing anomalies in `quarantine_chunks`. |
| `services/health_scorer.py` | Calculates real-time composite health indices. |
| `services/health_service.py` | Extend orchestrator to expose scheduled scan triggers and index queries. |

---

## 15. Data Flow

1. Cron trigger invokes `AutomatedHealthScheduler.run_scheduled_sweep(tenant_id)`.
2. Distributed lock `raguard:lock:health:{tenant_id}` is acquired via Redis.
3. `ParityRepairWorker` and `OrphanCleanupWorker` execute concurrently.
4. Corrupted chunks found during scans are routed to `QuarantineEngine.quarantine_chunks()`.
5. `KnowledgeHealthScoreEngine.refresh_index(tenant_id)` calculates updated $H_{\text{index}}$ and saves to database.

---

## 16. Sequence Diagrams

```
Cron -> AutomatedHealthScheduler: execute_sweep(tenant_id)
activate AutomatedHealthScheduler
AutomatedHealthScheduler -> RedisLock: acquire("lock:health:" + tenant_id)
RedisLock --> AutomatedHealthScheduler: lock_granted=True
AutomatedHealthScheduler -> ParityRepairWorker: repair_parity(tenant_id)
ParityRepairWorker -> IntegrityAuditor: verify_tenant_parity(tenant_id)
IntegrityAuditor --> ParityRepairWorker: parity_dto (mismatch detected)
ParityRepairWorker -> VectorService: delete_orphans(orphan_ids)
ParityRepairWorker -> IngestionQueue: enqueue_reindex(missing_ids)
AutomatedHealthScheduler -> HealthScorer: refresh_index(tenant_id)
HealthScorer -> HealthRepo: save_index(index_dto)
AutomatedHealthScheduler -> RedisLock: release()
AutomatedHealthScheduler --> Cron: sweep_completed
deactivate AutomatedHealthScheduler
```

---

## 17. Folder Structure Changes

```
backend/modules/knowledge_health/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── routes.py                 # [MODIFY] Add automated & index routes
├── cleanups/
│   ├── __init__.py
│   ├── orphans.py                # [PRESERVED]
│   ├── purge.py                  # [PRESERVED]
│   └── quarantine.py             # [NEW] Quarantine storage engine
├── models/
│   ├── __init__.py
│   ├── health_scan.py            # [PRESERVED]
│   └── quarantine_chunk.py       # [NEW] ORM model
├── repositories/
│   ├── __init__.py
│   └── health_repository.py      # [MODIFY] Add quarantine & index CRUD
├── schemas/
│   ├── __init__.py
│   ├── errors.py                 # [MODIFY] Add QuarantineError
│   └── health_dto.py             # [MODIFY] Add index/quarantine DTOs
├── services/
│   ├── __init__.py
│   ├── health_scorer.py          # [NEW] Composite health index engine
│   └── health_service.py         # [MODIFY] Add automation hooks
└── workers/
    ├── __init__.py
    ├── orphan_worker.py          # [NEW] Scheduled orphan sweeper
    ├── parity_worker.py          # [NEW] Scheduled parity repairer
    └── stale_worker.py           # [NEW] Scheduled stale scanner
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/knowledge_health/schemas/errors.py` | Modify | Add `QuarantineOperationError`, `LockAcquisitionFailed`. |
| `backend/modules/knowledge_health/schemas/health_dto.py` | Modify | Add `KnowledgeHealthIndexDTO`, `QuarantineChunkDTO`, `ParityRepairResultDTO`. |
| `backend/modules/knowledge_health/cleanups/quarantine.py` | New | Implements `QuarantineEngine` storing malformed vector records. |
| `backend/modules/knowledge_health/models/quarantine_chunk.py` | New | ORM entity `QuarantineChunkORM`. |
| `backend/modules/knowledge_health/services/health_scorer.py` | New | Implements `KnowledgeHealthScoreEngine`. |
| `backend/modules/knowledge_health/workers/orphan_worker.py` | New | Async Celery worker for scheduled orphan cleaning. |
| `backend/modules/knowledge_health/workers/parity_worker.py` | New | Async Celery worker for scheduled parity repair. |
| `backend/modules/knowledge_health/workers/stale_worker.py` | New | Async Celery worker for stale embedding scans. |
| `backend/modules/knowledge_health/services/health_service.py` | Modify | Integrate workers, scorer, and quarantine. |
| `backend/modules/knowledge_health/repositories/health_repository.py` | Modify | Add CRUD methods for `quarantine_chunks` and health scores. |
| `backend/modules/knowledge_health/api/routes.py` | Modify | Add endpoints `/api/v1/health/index/{tenant_id}`, `/api/v1/health/quarantine`. |
| `alembic/versions/0015_knowledge_health_automation.py` | New | Database migration table `quarantine_chunks`. |

---

## 19. Database Changes

### Table: `quarantine_chunks`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Unique quarantine entry ID |
| `chunk_id` | UUID | NOT NULL, INDEX | Original document chunk ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `reason` | VARCHAR(128) | NOT NULL | `EMBEDDING_MISMATCH`, `CORRUPTED_PAYLOAD`, `ORPHAN` |
| `raw_payload` | JSONB | NOT NULL | Preserved point metadata |
| `quarantined_at`| TIMESTAMP | NOT NULL | Quarantine timestamp |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health/index/{tenant_id}` | N/A | `KnowledgeHealthIndexDTO` | Fetch real-time composite knowledge health score |
| `POST` | `/api/v1/health/scan/schedule` | `ScheduleScanRequestDTO` | `HealthScanJobDTO` | Trigger asynchronous self-healing background sweep |
| `GET` | `/api/v1/health/quarantine` | N/A (`?tenant_id=...`) | `list[QuarantineChunkDTO]` | List quarantined vector chunks requiring manual inspection |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `HEALTH_CRON_SCHEDULE`: Default `"0 2 * * *"` (Daily at 2 AM UTC).
* `HEALTH_SWEEP_BATCH_SIZE`: Default `500`.
* `HEALTH_QUARANTINE_RETENTION_DAYS`: Default `30`.

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_HEALTH_CRON_SCHEDULE` | `0 2 * * *` | Cron schedule for background self-healing scans |
| `RAGUARD_HEALTH_LOCK_TIMEOUT_SEC` | `3600` | Redis distributed lock expiration time |
| `RAGUARD_HEALTH_AUTOMATION_ENABLED` | `true` | Feature flag enabling background maintenance workers |

---

## 23. Security Considerations

* **Tenant Isolation**: Every quarantine operation and worker job MUST scope SQL queries strictly to `tenant_id`.
* **Lock Expiration**: Redis distributed locks MUST include a TTL (`3600s`) to prevent deadlocks if a worker process terminates unexpectedly.

---

## 24. Performance Considerations

* **Throttled Purges**: When deleting large batches of orphaned points from Qdrant, workers must pause `10ms` between `500-point` chunks to preserve retrieval latency.
* **Non-Blocking Scoring**: `KnowledgeHealthScoreEngine` caches scores in Redis for `60 seconds` to prevent heavy index queries from slamming PostgreSQL during dashboard polling.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record spans `raguard.health.orphan_worker` and `raguard.health.parity_repair` recording `orphans_purged` and `parity_repaired`.
* **Prometheus Metrics**:
  * `raguard_knowledge_health_index_gauge{tenant_id}`
  * `raguard_quarantine_chunks_total{tenant_id, reason}`
  * `raguard_background_sweep_duration_seconds`

---

## 26. Error Handling Strategy

* Raise `LockAcquisitionFailed` if another worker instance already holds the Redis lock for a tenant scan.
* If Qdrant becomes unreachable during a background sweep, log error, release Redis lock cleanly in `finally` block, and reschedule for next window without throwing unhandled worker exceptions.

---

## 27. Testing Strategy

* **Unit Tests**: Test `KnowledgeHealthScoreEngine` math; test `QuarantineEngine` insertion; verify `ParityRepairWorker` identifies missing IDs accurately.
* **Integration Tests**: Verify distributed lock acquisition using mocked/redis containers and end-to-end `/api/v1/health/index/{tenant_id}` API behavior.
* **Regression Tests**: Ensure Phase 3 baseline `run_health_scan()` continues to operate cleanly.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/knowledge_health/test_health_scorer.py`: Verify health index math and boundary conditions (`0.0 - 100.0`).
* `tests/unit/backend/modules/knowledge_health/test_quarantine_engine.py`: Test quarantine storage and retention pruning.
* `tests/unit/backend/modules/knowledge_health/test_parity_worker.py`: Verify self-healing missing ID extraction.

---

## 29. Integration Testing Plan

* `tests/integration/test_health_automation_api.py`: Verify scheduled scan endpoints and quarantine listings.
* `tests/integration/test_health_workers.py`: Verify database migrations and Celery task execution on `quarantine_chunks`.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| Overzealous self-healing deleting valid points | Low | Critical | Move anomalies to `quarantine_chunks` first before permanent purge (`30-day` retention). |
| Background worker competing with heavy indexing | Medium | Medium | Run automated sweeps exclusively during low-traffic windows (`CRON_SCHEDULE = 0 2 * * *`). |

---

## 31. Acceptance Criteria

1. `KnowledgeHealthScoreEngine.refresh_index(tenant_id)` outputs `KnowledgeHealthIndexDTO` reflecting exact parity and orphan ratios.
2. `ParityRepairWorker` automatically repairs count mismatches without requiring manual human intervention.
3. Malformed chunks persist to `quarantine_chunks` table instead of being silently discarded.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/knowledge_health/`.
* Alembic migration `0015_knowledge_health_automation.py` applied.
* 100% of Phase 14 unit and integration tests passing alongside all Phase 0–13 tests.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m14_part1.py`)**: DTO extensions (`health_dto.py`), `QuarantineEngine`, and migration `0015_knowledge_health_automation.py` + ORM model.
* **Milestone 2 (`impl_m14_part2.py`)**: Implement `KnowledgeHealthScoreEngine` and `ParityRepairWorker`.
* **Milestone 3 (`impl_m14_part3.py`)**: Implement `OrphanCleanupWorker`, `StaleScannerWorker`, and REST API endpoints (`api/routes.py`).
* **Milestone 4 (`impl_m14_tests.py`)**: Execute unit (`test_health_scorer.py`, `test_quarantine_engine.py`) and integration tests.

---

## 34. Provider Abstraction

All vector storage repairs MUST go through `VectorStorageService` (`backend/modules/vector/services/vector_service.py`), ensuring Qdrant/Pinecone provider agnosticism.

---

## 35. Architecture Decision Records (ADR)

* **ADR-014-1**: Use quarantine tables (`quarantine_chunks`) instead of immediate hard deletion when vector points fail payload integrity verification.
* **ADR-014-2**: Enforce Redis distributed locking (`raguard:lock:health:{tenant_id}`) before executing any background synchronization worker.

---

## 36. Versioning Strategy

All new DTOs use `v2` where modifying existing structures (`HealthScanJobDTOv2`), while introducing new dedicated contracts (`KnowledgeHealthIndexDTO`) under API v1.

---

## 37. Feature Flags

`RAGUARD_HEALTH_AUTOMATION_ENABLED`: If `false`, scheduled workers skip execution immediately upon invocation while manual API scans remain functional.

---

## 38. Performance Budgets

* Health index calculation: `20ms` (cached for `60s`).
* Worker batch deletion pause: `10ms per 500 records`.
* Maximum lock hold duration: `3600 seconds`.

---

## 39. Deployment Architecture

Workers deploy as standalone Celery/asyncio worker processes (`celery -A backend.workers worker -l info`) consuming tasks from Redis message brokers.

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| Worker Process Crash During Lock | Lock Expiry TTL | Redis automatically drops expired lock after `3600s`, allowing next scheduled worker to resume. |
| Qdrant Network Timeout During Purge | `QdrantException` | Abort batch clean, preserve remaining items in database queue, emit retry event. |

---

## 41. Dependency Graph

```
Phase 1 (Ingestion) ──► Phase 14 (Automated Cleanup Engine) ──► Phase 5 (Retrieval Index)
                                       │
                                       ▼
                             PostgreSQL (`quarantine_chunks`)
```

---

## 42. Rollback Strategy

Set `RAGUARD_HEALTH_AUTOMATION_ENABLED=false` to stop background workers. Run `alembic downgrade 0014` to remove `quarantine_chunks`.

---

## 43. Success Metrics

* **Self-Healing Success Rate**: $> 99\%$ of parity discrepancies resolved automatically on first repair pass.
* **Quarantine Capture**: $100\%$ of malformed chunks isolated safely without accidental data loss.
* **Index Query Overhead**: Mean health index fetch latency $< 5\text{ms}$ (cached).

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Autonomous Background Sweeps | Section 5.3 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `OrphanCleanupWorker` |
| Self-Healing Parity Repair | Section 5.3 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `ParityRepairWorker` |
| Quarantine Storage | Section 5.3 | `DATABASE_DESIGN_AFTER_IMPROVEMENTS.md` | `QuarantineEngine` |

---

## 45. Implementation Checklist

- [ ] Create `schemas/errors.py` and update `schemas/health_dto.py`.
- [ ] Create `cleanups/quarantine.py` and `models/quarantine_chunk.py`.
- [ ] Create `services/health_scorer.py` and update `services/health_service.py`.
- [ ] Create `workers/orphan_worker.py`, `workers/parity_worker.py`, and `workers/stale_worker.py`.
- [ ] Update `repositories/health_repository.py` and `api/routes.py`.
- [ ] Create migration `0015_knowledge_health_automation.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m14_*.py`) executed cleanly.
- [ ] 100% of Phase 14 unit and integration tests passing (`test_health_*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] No Phase 3 baseline unit test regressions.

---

## 47. File Inventory

* **Modified Files**:
  * `backend/modules/knowledge_health/schemas/errors.py`
  * `backend/modules/knowledge_health/schemas/health_dto.py`
  * `backend/modules/knowledge_health/services/health_service.py`
  * `backend/modules/knowledge_health/repositories/health_repository.py`
  * `backend/modules/knowledge_health/api/routes.py`
* **New Files**:
  * `backend/modules/knowledge_health/cleanups/quarantine.py`
  * `backend/modules/knowledge_health/models/quarantine_chunk.py`
  * `backend/modules/knowledge_health/services/health_scorer.py`
  * `backend/modules/knowledge_health/workers/__init__.py`
  * `backend/modules/knowledge_health/workers/orphan_worker.py`
  * `backend/modules/knowledge_health/workers/parity_worker.py`
  * `backend/modules/knowledge_health/workers/stale_worker.py`
  * `alembic/versions/0015_knowledge_health_automation.py`
  * `tests/unit/backend/modules/knowledge_health/test_health_scorer.py`
  * `tests/unit/backend/modules/knowledge_health/test_quarantine_engine.py`
  * `tests/unit/backend/modules/knowledge_health/test_parity_worker.py`
  * `tests/integration/test_health_automation_api.py`

---

## 48. Cross-Phase Consistency Review

Phase 14 ensures that all `chunk_id` and `tenant_id` references match exact UUID and string formats used by Phase 1 (`ingestion`) and Phase 5 (`retrieval`). `KnowledgeHealthIndexDTO` directly feeds Phase 16 (`dashboard`) without requiring schema transforms.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Single responsibility cleanly segregated across scheduled workers (`OrphanCleanupWorker` vs `ParityRepairWorker`).
* **Clean Architecture**: Background workers depend strictly on domain services (`KnowledgeHealthOrchestrator`) and repository boundaries.
* **Concurrency**: Redis distributed locking guarantees thread safety across horizontal replicas.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Add `workers/` subdirectory and populate `cleanups/quarantine.py`, `services/health_scorer.py`.
* **Database**: Migration `0015_knowledge_health_automation.py` creating `quarantine_chunks`.
* **API Inventory**: `GET /api/v1/health/index/{tenant_id}`, `POST /api/v1/health/scan/schedule`, `GET /api/v1/health/quarantine`.
* **Milestone Scripts**: `impl_m14_part1.py`, `impl_m14_part2.py`, `impl_m14_part3.py`, `impl_m14_tests.py`.
