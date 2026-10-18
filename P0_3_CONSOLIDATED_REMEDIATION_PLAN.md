# Veritas-RAG P0-3 — Master Consolidated Batch Remediation & Acceptance Plan

**Document Date:** 2026-10-18  
**Repository:** `D:\RAGuard`  
**Git HEAD:** `4df1cd98e1438772adcd73d997eff32e4354c0d5`  
**Certification Target:** Milestone P0-3 End-to-End Verification & Release Certification  
**Status:** `P0-3 BLOCKED — APPROVAL OR EVIDENCE REQUIRED`

---

## 1. Executive Summary & Strategy

This master remediation plan integrates all findings from `P0_3_CONSOLIDATED_FORENSIC_FINDINGS.md` and establishes the definitive, evidence-based execution protocol for Veritas-RAG P0-3 certification.

### Core Principles:
1. **Consolidated Batch Remediation**: Implement all approved code and migration fixes in dependency-ordered batches without piece-meal trial-and-error cycles.
2. **Comprehensive Acceptance Matrix**: P0-3 certification is not merely a passing migration and six lifecycle tests. It requires satisfying all 18 mandatory architectural and operational criteria with verifiable evidence.
3. **Cryptographic Build Provenance**: The dedicated E2E worker image must be built directly from the verified source snapshot with cryptographic labels embedded during the build; retagging is strictly prohibited.
4. **Non-Destructive Reverse-Patch Rollback**: Pre-batch diffs are captured before edits. Rollbacks occur exclusively via targeted reverse patches. `git reset`, `git clean`, and `git stash` remain strictly prohibited.
5. **Strict Isolation**: All live database, broker, vector, and worker interactions execute on disposable E2E ports (`5433`, `6389`, `6343`, `6344`). Development services (`5432`, `6379`, `6333`, `8000`, `5173`) remain 100% untouched.

---

## 2. Complete P0-3 Acceptance Matrix (18 Criteria)

| # | Invariant / Acceptance Criterion | Verification Command / Target | Evidence Required | Current Status | New Test Needed? |
|---|---|---|---|---|---|
| **1** | **Fresh Database Migration** | `alembic upgrade head` on isolated PostgreSQL 15 (port 5433) | Exit code 0; `alembic_version` contains `wh_01_webhook_crypto`; 0 migration errors from base `0001` | BLOCKED (by `MIG-004`) | No (executed in Phase C) |
| **2** | **Schema & Model Consistency** | Database catalog vs ORM inspection script on port 5433 | 0 schema discrepancies; `tenant_quotas.workspace_id`, `notification_delivery_logs.payload_snapshot`, `workspace_webhooks.encrypted_secret`, `processing_jobs.dispatch_state` verified | UNVERIFIED | No (automated in Phase C gate) |
| **3** | **Official Ingestion Fixture Creation** | `DocumentService.upload_document` & `upload_new_version` via `LocalStorageProvider` | Storage artifacts created in scratch storage; valid rows in `documents`, `document_versions`, `storage_objects`, `processing_jobs` | PASS in Run 0 (Prior Run) | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **4** | **V1 Activation & Retrievability** | `test_p0_3_lifecycle_e2e.py` Step 1 | `Document.status == READY`, `Document.latest_version_id == v1_id`, `v1.is_active_vector == True` | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **5** | **V2 In-Flight Zero Downtime** | `test_p0_3_lifecycle_e2e.py` Step 2 (pause indexing queue) | While V2 embedding finishes, `Document.status == READY`, `Document.latest_version_id == v1_id`, `v2.is_active_vector == False` | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **6** | **V2 Synchronous Promotion** | `test_p0_3_lifecycle_e2e.py` Step 3 (resume indexing queue) | Upon vector sync completion: `Document.latest_version_id == v2_id`, `v2.is_active_vector == True`, `v1.is_active_vector == False` | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **7** | **Stale-Event Monotonic Rejection** | `test_p0_3_lifecycle_e2e.py` Step 4 | Delivering out-of-order V1 event does not regress document: `Document.latest_version_id == v2_id` retained, `v1.is_active_vector == False` retained | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **8** | **Parser Ingestion Failure Resilience** | `test_p0_3_lifecycle_e2e.py` Step 5 (corrupted V3 payload) | `ProcessingJob.status == "FAILED"`, while `Document.status == READY` and `Document.latest_version_id == v2_id` retained | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **9** | **Downstream Failure Recovery & Active-Version Preservation** | `pytest backend/tests/unit/services/test_failure_service.py` (expanded suite) | When V1 is active, failures in V2 at chunking, embedding, or vector sync leave `Document.status == READY`. When no active version exists (initial V1), `Document.status == FAILED` | BLOCKED (by `LFC-001`) | **YES** (expand `test_failure_service.py` in Batch 2) |
| **10** | **Dense & BM25 Active-Version Agreement** | `test_p0_3_lifecycle_e2e.py` Step 6 | Qdrant dense search and BM25 keyword search both return V2 candidate chunks; superseded V1 chunks rejected by DB gate | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **11** | **PostgreSQL, Qdrant & Storage Consistency** | `test_p0_3_lifecycle_e2e.py` Step 6 candidate validation | Exact matching of chunk UUIDs, document UUIDs, version UUIDs across PostgreSQL `document_chunks`, Qdrant point payloads, and local storage | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **12** | **Multi-Tenant Boundary Isolation** | `test_p0_3_lifecycle_e2e.py` Step 6 (Tenant A vs B) | Dense search on Collection A with Tenant B filter returns 0 hits; BM25 candidate sets disjoint; cross-tenant candidate validation probe returns 0 candidates | PASS in Run 0 | No (covered in `test_p0_3_lifecycle_e2e.py`) |
| **13** | **Authenticated Grounded Chat & Citations** | `pytest tests/integration/test_epic8_r3_real.py tests/integration/test_epic8_r0_routing.py` | Chat orchestrator generates grounded response citing active chunks; cross-tenant retrieval yields 0 citations from other tenants | UNVERIFIED on current HEAD | No (existing integration suite) |
| **14** | **SSE Streaming & Frontend Replay** | `pytest tests/integration/test_epic8_r3_real.py::test_epic8_r3_real_sse_orchestration` | `stream_chat` yields well-formed SSE chunks (`event: token`, `event: citation`, `event: done`); `Last-Event-ID` reconnection replay verified | UNVERIFIED on current HEAD | No (existing integration suite) |
| **15** | **Chat Persistence Across Sessions** | `pytest tests/integration/test_epic8_r3_real.py` | Query messages and assistant replies persisted to `chat_messages` table and reloaded by session ID | UNVERIFIED on current HEAD | No (existing integration suite) |
| **16** | **Failure-Path & Cancellation Regression** | `pytest tests/integration/test_epic8_r3_real.py` (cancellation & timeout tests) | Disconnect / client cancellation triggers partial response persistence with cancellation flag; timeouts handled cleanly without leaking transactions | UNVERIFIED on current HEAD | No (existing integration suite) |
| **17** | **Task Queue Quiescence & Distributed Ordering Scope** | `drain_celery_queues_and_verify_quiescence` across all 7 queues | All 7 Celery queues drained to 0; worker idle; explicit documentation distinguishing handler monotonicity from physical broker reordering | PASS in Run 0 | No (covered in harness teardown) |
| **18** | **Run-Scoped Cleanup & Repository Preservation** | `run_e2e.ps1` teardown & post-run `git status` | Dedicated containers, volumes, networks, and scratch folders purged; host ports verified free; zero repository modifications or deletions | PASS in Run 0 | No (covered in harness teardown) |

---

## 3. Dependency-Ordered Implementation Batches

### Pre-Batch Safety Step: Working Tree Baseline Capture
Before modifying any file in Batch 1 or Batch 2:
1. Record Git HEAD and run `git diff > scratch/pre_batch_remediation.patch`.
2. Confirm working tree status has only the 20 pre-existing baseline modified files and the 3 authorized migration changes.

---

### Batch 1: Migration Blocker Remediation (`MIG-004`)

#### 1. Scope and Target
- **Target File**: `backend/database/migrations/versions/20260928_reconcile_notification_delivery_logs.py`
- **Revision ID**: `chat_001_notif_logs`
- **Down-Revision**: `e15_iss004_policies`

#### 2. Detailed Forensic Rationale & Boundary Analysis
- **Migration Purpose**:
  Revision `chat_001_notif_logs` was added to reconcile older out-of-band development databases that lacked modern columns on `notification_delivery_logs`.
- **Operations in `upgrade()`**:
  - Adds `payload_snapshot` (`JSONB`, NOT NULL)
  - Adds `attempt_count` (`Integer`, NOT NULL)
  - Adds `is_deleted` (`Boolean`, NOT NULL)
  - Drops `notification_id`
  - Drops `retry_count`
- **Operations in `downgrade()`**:
  - Restores `notification_id` and `retry_count`
  - Drops `is_deleted`, `attempt_count`, `payload_snapshot`
- **Why Safe on Canonical Fresh Database**:
  In `20260815_6c11701a28c5_epic11_notifications.py` (lines 24–38), table `notification_delivery_logs` was initially created with `payload_snapshot`, `attempt_count`, and `is_deleted`, and without `notification_id` or `retry_count`. On a fresh database following canonical history, calling `op.add_column` triggers `DuplicateColumnError`, and `op.drop_column` targets missing columns.
  Replacing both `upgrade()` and `downgrade()` with `pass` makes this revision a clean no-op on the canonical line, preserving revision ID `chat_001_notif_logs`, parent `e15_iss004_policies`, and full DAG continuity.
- **External Database Boundary**:
  The schema state of any external staging, production, or shared database is **UNKNOWN**. No claims are made that editing this migration reconciles already-applied external databases, nor will external databases be accessed or modified.

#### 3. Exact Implementation
In `backend/database/migrations/versions/20260928_reconcile_notification_delivery_logs.py`:
- Replace lines 24–57 (`def upgrade() -> None: ...`) with:
  ```python
  def upgrade() -> None:
      pass
  ```
- Replace lines 59–86 (`def downgrade() -> None: ...`) with:
  ```python
  def downgrade() -> None:
      pass
  ```

#### 4. Verification Gate 1
- `git diff --check`
- Python AST verification: `python -m py_compile backend/database/migrations/versions/20260928_reconcile_notification_delivery_logs.py`
- ScriptDirectory DAG validation: Single Head (`wh_01_webhook_crypto`), Single Base (`0001`), 68 revisions.
- Pytest offline manifest tests: `.\venv\Scripts\pytest tests/e2e/test_manifest_offline.py -v`.

---

### Batch 2: Document Lifecycle Zero-Downtime Serving Hardening (`LFC-001`)

#### 1. Scope and Target
- **Target File**: `backend/document/services/failure_service.py`
- **Class / Method**: `PipelineFailureSynchronizer.record_pipeline_failure`

#### 2. Detailed Technical Rationale & Code Inspection
- **Current Defect**:
  In `failure_service.py` lines 49–55, `doc.status` is unconditionally set to `DocumentStatus.FAILED` regardless of whether the document already has an active vector version serving user traffic. This violates Acceptance Criterion 9.
- **Inspection of Models and Contracts**:
  - `Document` model has `id`, `tenant_id`, `status`, `latest_version_id`, `updated_at`.
  - `DocumentVersion` model has `id`, `document_id`, `tenant_id`, `is_active_vector`, `is_deleted`.
  - `ProcessingJob` model has `id`, `document_id`, `version_id`, `status`.
  - `EmbeddingJob` model has `id`, `document_id`, `document_version_id`, `status`.
- **Exact Surgical Modification**:
  Before altering `doc.status`, identify whether a non-failing version has `is_active_vector == True`, scoped to the resolved tenant and non-deleted versions:
  ```python
  # 1. Update Document status: preserve READY if another active version exists
  doc = await session.get(Document, document_id)
  resolved_tenant_id = tenant_id or (doc.tenant_id if doc else "unknown")
  if doc:
      failing_version_id = (
          (target_job.version_id if target_job else None)
          or (emb_job.document_version_id if emb_job else None)
      )
      all_versions_stmt = (
          select(DocumentVersion)
          .where(
              DocumentVersion.document_id == document_id,
              DocumentVersion.tenant_id == resolved_tenant_id,
              DocumentVersion.is_deleted.is_(False),
          )
      )
      all_versions = (await session.execute(all_versions_stmt)).scalars().all()
      has_active_version = any(
          v.is_active_vector and (failing_version_id is None or v.id != failing_version_id)
          for v in all_versions
      )
      if has_active_version:
          doc.status = DocumentStatus.READY
          logger.info(
              "Preserved Document READY status after in-flight version failure",
              document_id=str(document_id),
              failing_stage=failing_stage,
          )
      else:
          doc.status = DocumentStatus.FAILED
      doc.updated_at = now
  ```

#### 3. Verification Gate 2 (Expanded Test Suite)
Expand `backend/tests/unit/services/test_failure_service.py` with rigorous coverage:
1. `test_failure_synchronizer_active_v1_retained_on_v2_chunking_failure`: Verifies `doc.status == READY` when V1 is active and V2 fails chunking.
2. `test_failure_synchronizer_active_v1_retained_on_v2_embedding_failure`: Verifies `doc.status == READY` when V1 is active and V2 fails embedding.
3. `test_failure_synchronizer_active_v1_retained_on_v2_vector_sync_failure`: Verifies `doc.status == READY` when V1 is active and V2 fails vector sync.
4. `test_failure_synchronizer_initial_v1_failure_sets_failed`: Verifies `doc.status == FAILED` when no active version exists.
5. `test_failure_synchronizer_missing_job_metadata_fallback`: Verifies graceful fallback when job/version IDs are absent.
6. `test_failure_synchronizer_ignores_soft_deleted_active_version`: Verifies that a soft-deleted version (`is_deleted=True`) with `is_active_vector=True` is ignored.
7. `test_failure_synchronizer_tenant_scoping`: Verifies versions from other tenants are never considered.
8. `test_failure_synchronizer_forensic_diagnostics_and_event_log`: Verifies `FailedJobDiagnostics` and `DocumentEventLog` entries are persisted.
- **Execution Command**:
  `.\venv\Scripts\pytest backend/tests/unit/services/test_failure_service.py -v`

---

## 4. Phase C: Isolated Full Migration Validation Protocol

- **Port**: `5433` (dedicated host port).
- **Container**: Disposable PostgreSQL 15 instance `raguard-e2e-postgres-val4_<run_id>`.
- **Target Database**: `raguard_test_db`.
- **Execution**:
  ```powershell
  docker run -d --name raguard-e2e-postgres-val4 -p 5433:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=raguard_test_db postgres:15-alpine
  ```
  Wait for health, then execute:
  ```powershell
  $env:ALEMBIC_DATABASE_URL = "postgresql://postgres:postgres@localhost:5433/raguard_test_db"
  alembic upgrade head
  ```
- **Validation Gate 3 (Schema & Catalogs)**:
  1. Confirm `alembic_version` contains `wh_01_webhook_crypto`.
  2. Execute automated schema validation verifying:
     - `tenant_quotas.workspace_id` column and index exist.
     - `notification_delivery_logs.payload_snapshot` (`JSONB`), `attempt_count` (`int`), `is_deleted` (`bool`) exist.
     - `workspace_webhooks.encrypted_secret` (`Text`) exists.
     - `processing_jobs.dispatch_state` (`VARCHAR(50)`) exists.
     - `documents.source_type` (`VARCHAR(50)`) exists.
     - `workspaces.public_id` (`VARCHAR(50)`, NOT NULL, unique index) exists.
  3. Clean teardown of disposable container and volume. Port 5433 verified free.

---

## 5. Phase D & E: Worker Image Provenance & Live E2E Certification

### 1. Mandatory Worker Image Provenance Build
Per user requirement, **retagging is strictly prohibited**. The dedicated E2E worker image must be built from the exact working-tree source snapshot:
1. Calculate canonical working-tree source digest:
   ```powershell
   $sourceDigest = (& ".\venv\Scripts\python.exe" tests/e2e/manifest.py digest).Trim()
   $expectedImage = "veritas-rag:e2e-$sourceDigest"
   ```
2. Build the image with required provenance labels:
   ```powershell
   docker build -t $expectedImage --label "veritas.rag.source_digest=$sourceDigest" -f Dockerfile .
   ```
3. Inspect and verify:
   - Image ID matches `sha256:[0-9a-fA-F]{64}`.
   - Image label `veritas.rag.source_digest` matches `$sourceDigest`.
   - Preflight offline check passes: `.\venv\Scripts\pytest tests/e2e/test_manifest_offline.py -v`.

### 2. Live P0-3 Lifecycle E2E Execution
Execute the master PowerShell harness:
```powershell
.\tests\e2e\run_e2e.ps1 -Execute
```
- **Live Scenarios Executed**:
  - Scenario 1: Zero-downtime V1 retrievability while V2 is in-flight.
  - Scenario 2: Synchronous V2 promotion upon vector synchronization.
  - Scenario 3A: Parser/ingestion failure preserves active version retrievability.
  - Scenario 4: Stale vector-sync event monotonic gate rejection.
  - Scenario 5: Dense and BM25 active-version agreement using real chunk records.
  - Scenario 6: Multi-tenant boundary isolation using real Tenant A & B chunks.

### 3. Integrated Chat & Streaming Verification
Run the integrated chat and streaming suite to verify Acceptance Criteria 13, 14, 15, and 16:
```powershell
.\venv\Scripts\pytest tests/integration/test_epic8_r3_real.py tests/integration/test_epic8_r0_routing.py -v
```

### 4. Teardown & Quiescence Verification
Verify the harness automatically drains all 7 Celery queues, stops the worker container, cleans up run-scoped database records, drops run-scoped Qdrant collections, purges scratch storage, and removes disposable containers and volumes.

---

## 6. Non-Destructive Rollback & Recovery Strategy

| Layer | Potential Failure | Non-Destructive Rollback Procedure |
|---|---|---|
| **Batch 1 (Migrations)** | Syntax or DAG validation error | Apply reverse patch only for `20260928_reconcile_notification_delivery_logs.py` using preserved diff. Zero impact on other migrations. |
| **Batch 2 (Lifecycle)** | Unit test failure in `test_failure_service.py` | Reverse only edits to `backend/document/services/failure_service.py` using preserved diff. |
| **Phase C (Migration Val)** | Postgres migration failure on port 5433 | Stop and remove container `raguard-e2e-postgres-val4`. Port 5433 immediately free. Zero impact on port 5432 dev database. |
| **Phase D (Image Build)** | Docker build error | Working tree untouched. Inspect Docker build log. |
| **Phase E (Live E2E)** | Pytest assertion timeout or failure | Harness `finally` block tears down `raguard-e2e-*` containers and volumes. Ports 5433, 6389, 6343 released. |

**Repository Safety Mandate**:
- Never run `git reset --hard` or `git reset`.
- Never run `git clean -fd` or `git clean`.
- Never run `git stash`.
- Preserve all 20 pre-existing baseline modified files and all untracked test fixtures and reports.

---

## 7. Certification Decision Protocol

The final certification status reported in `P0_3_MASTER_EXECUTION_REPORT.md` will strictly evaluate against the 18 criteria:
- **`P0-3 CERTIFIED — ALL REQUIRED CHECKS PASSED`**: All 18 criteria in the acceptance matrix are proven with live execution evidence and zero errors.
- **`P0-3 NOT CERTIFIED — REQUIRED CHECKS FAILED`**: Any of the 18 mandatory criteria fails during execution.
- **`P0-3 BLOCKED — APPROVAL OR EVIDENCE REQUIRED`**: Current status prior to user batch authorization.
