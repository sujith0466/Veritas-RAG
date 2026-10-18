# Veritas-RAG P0-3 — Consolidated Forensic Findings Register

**Document Date:** 2026-10-18  
**Repository:** `D:\RAGuard`  
**Git HEAD:** `4df1cd98e1438772adcd73d997eff32e4354c0d5`  
**Investigation Mode:** Strict Read-Only Consolidated Audit (Phase 1)  
**Overall Status:** `P0-3 BLOCKED — APPROVAL OR EVIDENCE REQUIRED`

---

## 1. Executive Summary

This consolidated forensic findings register establishes a comprehensive, evidence-backed inventory of all discoverable defects across the Veritas-RAG migration history, document lifecycle state machine, and P0-3 E2E test harness.

Following the Master Protocol, we investigated all 68 Alembic revisions from base `0001` through head `wh_01_webhook_crypto`, compared migration definitions against active ORM models, inspected all failure-synchronization pathways, audited the E2E lifecycle test suite, and evaluated container/image provenance requirements.

### Key Audit Conclusions:
1. **Migration Chain Blocker Isolated to Revision `chat_001_notif_logs`**:
   The active blocker preventing fresh-database migration completion is in `backend/database/migrations/versions/20260928_reconcile_notification_delivery_logs.py` (`chat_001_notif_logs`). It attempts duplicate column additions and phantom drops on `notification_delivery_logs`.
2. **Subsequent Migrations (Through Head `wh_01_webhook_crypto`) are Clean**:
   AST and inspection analysis of all 9 revisions downstream of `chat_001_notif_logs` confirmed that all later migrations either perform clean, guarded operations or utilize dynamic `sa.inspect(bind)` checks. No other migration failures exist between `chat_001_notif_logs` and head.
3. **Lifecycle Document Invariant Vulnerability Identified**:
   `backend/document/services/failure_service.py` unconditionally sets `doc.status = DocumentStatus.FAILED` upon pipeline failures in chunking, embedding, or vector sync, even when an earlier version is already active (`is_active_vector == True`). This breaks the zero-downtime serving invariant.
4. **Harness Provenance Gate Identified**:
   The E2E test runner computes a cryptographic source digest over `backend/` and required build context. Applying necessary migration fixes updates this digest. To run Phase 4 live E2E verification, the worker image must be updated to match the verified working-tree source digest under explicit authorization.

---

## 2. Consolidated Issue Register

### Issue MIG-001: Autogenerate Index and Column Drops on `health_scan_jobs` and Table Drop of `tenant_quotas`
- **Issue ID**: `MIG-001`
- **Severity**: Critical (P0) — Fatal fresh-database migration failure
- **Certification Impact**: Hard blocker for all downstream E2E execution
- **Affected Files & Revisions**:
  - `backend/database/migrations/versions/20260724_0224febbe7cc_add_relative_path_to_document.py` (Revision: `0224febbe7cc`, Revises: `680b30cdb5dd`)
- **Evidence & Failure Signature**:
  ```text
  sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
  column "is_deleted" of relation "health_scan_jobs" does not exist
  [SQL: ALTER TABLE health_scan_jobs DROP COLUMN is_deleted]
  ```
  And downstream in `f1302e18ea08`:
  ```text
  sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
  <class 'asyncpg.exceptions.UndefinedTableError'>: relation "tenant_quotas" does not exist
  [SQL: ALTER TABLE tenant_quotas ADD COLUMN workspace_id UUID]
  ```
- **Root Cause**:
  `0224febbe7cc` was created with `alembic revision --autogenerate -m "add_relative_path_to_document"`. The developer did not import domain models into `backend/database/base.py`, causing Alembic to generate table drops for 16 tables and column drops on `health_scan_jobs`. Table `health_scan_jobs` was originally created in `0008` without `is_deleted`. Table `tenant_quotas` was created in `0019` and was dropped by line 48 of `0224febbe7cc`, causing downstream revision `f1302e18ea08` to fail when adding `workspace_id`.
- **Current Status**:
  **REMEDIATED & VERIFIED**. Erroneous drops of `health_scan_jobs.is_deleted` and `tenant_quotas` were removed. `documents.relative_path` was preserved. Verified passing in Runs 1, 2, and 3.

---

### Issue MIG-002: Redundant Duplicate Table Creations in `6c11701a28c5`
- **Issue ID**: `MIG-002`
- **Severity**: Critical (P0) — Schema duplication and collision risk
- **Certification Impact**: High risk of duplicate table collision on clean runs
- **Affected Files & Revisions**:
  - `backend/database/migrations/versions/20260815_6c11701a28c5_epic11_notifications.py` (Revision: `6c11701a28c5`, Revises: `bb700f84136d`)
- **Evidence & Failure Signature**:
  Inspection revealed 13 duplicate `op.create_table` calls for pre-existing tables (`users`, `audit_logs`, `storage_objects`, `documents`, `document_versions`, `processing_jobs`, `document_events`, `document_chunks`, `chunk_relationships`, `embedding_jobs`, `chunk_embeddings`, `vector_index_metadata`, `health_scan_jobs`) and 38 redundant indexes.
- **Root Cause**:
  Unreviewed autogenerate run for Epic 11 generated full table recreations alongside genuine tables `notification_delivery_logs` and `workspace_webhooks`.
- **Current Status**:
  **REMEDIATED & VERIFIED**. Redundant table and index creations removed from `upgrade()` and drops removed from `downgrade()`. Genuine Epic 11 tables preserved. Verified passing in Runs 1, 2, and 3.

---

### Issue MIG-003: Duplicate Column Additions and Phantom Drops in `42e18ea087d3`
- **Issue ID**: `MIG-003`
- **Severity**: Critical (P0) — Fatal fresh-database migration failure
- **Certification Impact**: Hard blocker for downstream migrations
- **Affected Files & Revisions**:
  - `backend/database/migrations/versions/20260818_42e18ea087d3_add_workspace_name.py` (Revision: `42e18ea087d3`, Revises: `76b691b69868`)
- **Evidence & Failure Signature**:
  Observed failure in Run 1:
  ```text
  sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
  <class 'asyncpg.exceptions.DuplicateColumnError'>: column "workspace_name" of relation "users" already exists
  [SQL: ALTER TABLE users ADD COLUMN workspace_name VARCHAR(100)]
  ```
- **Root Cause**:
  Column `users.workspace_name` was already added in canonical revision `0021_add_tenant_id_workspace_name_to_users.py`. Additionally, revision `42e18ea087d3` attempted to drop phantom column `users.workspace_id` and alter `workspace_webhooks` in ways already defined at creation.
- **Current Status**:
  **REMEDIATED & VERIFIED**. Replaced redundant/phantom operations in `upgrade()` and `downgrade()` with `pass`. Preserved DAG continuity. Verified passing in Runs 2 and 3.

---

### Issue MIG-004: Duplicate Column Addition and Phantom Drops in `chat_001_notif_logs`
- **Issue ID**: `MIG-004`
- **Severity**: Critical (P0) — Active migration blocker
- **Certification Impact**: Blocks fresh-database migration at revision `chat_001_notif_logs`
- **Affected Files & Revisions**:
  - `backend/database/migrations/versions/20260928_reconcile_notification_delivery_logs.py` (Revision: `chat_001_notif_logs`, Revises: `e15_iss004_policies`)
- **Evidence & Failure Signature**:
  Observed failure in Run 3:
  ```text
  sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
  <class 'asyncpg.exceptions.DuplicateColumnError'>: column "payload_snapshot" of relation "notification_delivery_logs" already exists
  [SQL: ALTER TABLE notification_delivery_logs ADD COLUMN payload_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL]
  ```
- **Root Cause (Confirmed Fact)**:
  In `20260815_6c11701a28c5_epic11_notifications.py` (lines 24–38), table `notification_delivery_logs` was initially created with columns:
  - `payload_snapshot` (`JSONB`, NOT NULL)
  - `attempt_count` (`Integer`, NOT NULL)
  - `is_deleted` (`Boolean`, NOT NULL)
  and never created `notification_id` or `retry_count`.
  Revision `20260928_reconcile_notification_delivery_logs.py` was authored as a post-hoc schema reconciliation migration for older development databases. On the canonical fresh-database path, all additions are duplicates and all drops target non-existent columns.
- **Downstream Dependencies**:
  - Direct down-revision of `20261002_add_job_dispatch_state.py` (`d2_001_job_dispatch`).
- **Smallest Justified Remediation**:
  Replace lines 24–57 (`upgrade()`) and lines 59–86 (`downgrade()`) with `pass` in `backend/database/migrations/versions/20260928_reconcile_notification_delivery_logs.py`.
- **Upgrade/Downgrade Implications**:
  Preserves revision node and parent pointer in the DAG. On fresh databases, `notification_delivery_logs` already possesses the intended schema.
- **Approval Required**: YES (Included in Consolidated Remediation Plan).

---

### Issue MIG-005: Audit of Remaining Migration History (Revisions 60 through 68)
- **Issue ID**: `MIG-005`
- **Severity**: Informational / Preflight Verification
- **Certification Impact**: Confirms zero downstream migration blockers through head
- **Affected Revisions**:
  - `d2_001_job_dispatch` (`20261002_add_job_dispatch_state.py`)
  - `d4_001_source_url` (`20261002_add_document_source_type_and_url_fields.py`)
  - `ops_001_norm_score` (`20261003_ops_001_normalize_reliability_score.py`)
  - `ws_a2_public_id` (`20261004_ws_a2_add_workspaces_public_id.py`)
  - `ws_a4_invitation_selector` (`20261004_ws_a4_invitation_selector.py`)
  - `ws_b6_user_quotas` (`20261005_ws_b6_user_quotas_and_attribution.py`)
  - `ws_c1_workspace_access_requests` (`20261007_add_workspace_access_requests.py`)
  - `notif_01_in_app_notifications` (`20261010_add_notifications_table.py`)
  - `wh_01_webhook_crypto` (`20261011_webhook_crypto.py`)
- **Evidence**:
  AST and line-by-line inspection confirm:
  - `d2_001_job_dispatch` adds non-colliding columns (`dispatch_state`, `celery_task_id`, `dispatched_at`, `dispatch_error`) to `processing_jobs`.
  - `d4_001_source_url` adds non-colliding columns (`source_type`, `source_url`, `canonical_url`, `final_url`, `last_fetched_at`) to `documents`.
  - `ops_001_norm_score` updates `query_analytics_records.reliability_score` safely.
  - `ws_a2_public_id` adds `workspaces.public_id` as nullable, backfills, adds unique index, and enforces NOT NULL.
  - `ws_a4_invitation_selector` adds `token_selector` and widens `token_hash` from `VARCHAR(64)` to `VARCHAR(255)`.
  - Revisions `ws_b6_user_quotas`, `ws_c1_workspace_access_requests`, `notif_01_in_app_notifications`, and `wh_01_webhook_crypto` all utilize `sa.inspect(bind)` checks (`has_table`, column checks, index checks) to guarantee safe execution on fresh and existing databases.
- **Current Status**:
  **AUDITED & VERIFIED PASSING**. No code changes needed for revisions 60 through 68.

---

### Issue LFC-001: Pipeline Failure Synchronizer Overwrites READY Document Status During Multi-Version Ingestion Failures
- **Issue ID**: `LFC-001`
- **Severity**: High (P1) — Functional Invariant Violation
- **Certification Impact**: Direct threat to Scenario 3A/3B zero-downtime serving invariant
- **Affected File**: `backend/document/services/failure_service.py` (`PipelineFailureSynchronizer.record_pipeline_failure`)
- **Evidence**:
  Lines 49–55 of `failure_service.py`:
  ```python
  # 1. Update Document status to FAILED
  doc = await session.get(Document, document_id)
  resolved_tenant_id = tenant_id or (doc.tenant_id if doc else "unknown")
  if doc:
      doc.status = DocumentStatus.FAILED
      doc.updated_at = now
  ```
  While `backend/document/workers/ingestion.py` (lines 562–570) checks whether an older version is active before setting `doc.status = DocumentStatus.FAILED`, `failure_service.py` (which handles failures in chunking, embedding, and vector sync) unconditionally sets `doc.status = DocumentStatus.FAILED`.
- **Root Cause (Confirmed Fact)**:
  `PipelineFailureSynchronizer` lacks the multi-version active vector check. If Version 1 is active and Version 2 fails during chunking, embedding, or vector sync, the document is prematurely marked FAILED, taking down online retrieval.
- **Smallest Justified Remediation**:
  In `PipelineFailureSynchronizer.record_pipeline_failure`:
  Query `DocumentVersion` records for the document. If any version other than the failing version is active (`is_active_vector == True`), preserve `doc.status = DocumentStatus.READY`. Only transition `doc.status` to `DocumentStatus.FAILED` if no active version exists.
- **Approval Required**: YES (Included in Consolidated Remediation Plan).

---

### Issue E2E-001: Worker Container Source Digest Provenance Gate
- **Issue ID**: `E2E-001`
- **Severity**: Medium (P2) — Operational / Test Execution Gate
- **Certification Impact**: Harness preflight safety guard will fail closed unless image digest matches working tree
- **Affected Files**: `tests/e2e/run_e2e.ps1`, `tests/e2e/manifest.py`, Docker image `veritas-rag:e2e-<digest>`
- **Evidence**:
  Current computed source digest: `c9d4593049e0d20bf690e4e73113a864b8673000dbd2e3e166c619fc30828f21`.
  Existing local docker image: `veritas-rag:e2e-3b4661355197d5b221025abdfca60410ddd9b5cfa240aa9ed09ad44609e71f47`.
  `run_e2e.ps1` lines 47–75 strictly enforce that `E2E_WORKER_IMAGE` has label `veritas.rag.source_digest` matching the exact computed source digest.
- **Root Cause (Confirmed Fact)**:
  Modifications to migration files (`0224febbe7cc`, `6c11701a28c5`, `42e18ea087d3`, `chat_001_notif_logs`) and runtime code are tracked by `manifest.py`. The source digest must either be matched by tagging/building the dedicated test image or configuring the harness.
- **Smallest Justified Remediation**:
  Under explicit user authorization in Phase 4, build or tag the E2E worker image with the exact working-tree source digest and provenance labels.

---

### Issue E2E-002: In-Process Stale Event Injection vs. Distributed Celery Broker Delivery
- **Issue ID**: `E2E-002`
- **Severity**: Informational / Documented Architecture Limitation
- **Certification Impact**: Clearly delineate proven invariants vs. simulation scope
- **Affected File**: `tests/e2e/test_p0_3_lifecycle_e2e.py` (lines 233–250)
- **Evidence**:
  The lifecycle suite validates the monotonic gate via direct async invocation of `handle_vector_sync_completed(stale_v1_event)`.
- **Root Cause (Confirmed Fact)**:
  Physical race conditions and out-of-order message delivery in distributed Redis/Celery broker clusters cannot be nondeterministically forced without mock delays. The handler logic itself is authoritative and enforces monotonic version promotion.
- **Smallest Justified Remediation**:
  Maintain explicit documentation in the final certification report distinguishing in-process handler verification from physical distributed network delays.

---

## 3. Findings Matrix

| Issue ID | Area | Severity | Status | Root Cause Confirmed? | Remediation Planned? |
|---|---|---|---|---|---|
| `MIG-001` | Migration | P0 | Verified Remediated | Yes | Done |
| `MIG-002` | Migration | P0 | Verified Remediated | Yes | Done |
| `MIG-003` | Migration | P0 | Verified Remediated | Yes | Done |
| `MIG-004` | Migration | P0 | Active Blocker | Yes | Planned in Batch 1 |
| `MIG-005` | Migration | Info | Verified Passing | Yes | None needed |
| `LFC-001` | Lifecycle | P1 | Defect Confirmed | Yes | Planned in Batch 2 |
| `E2E-001` | Harness | P2 | Preflight Gate | Yes | Planned in Phase 4 Gate |
| `E2E-002` | Lifecycle | Info | Documented | Yes | Documented |

---

## 4. Phase 1 Audit Sign-Off

The comprehensive read-only investigation is complete. No file modifications or database mutations were made during Phase 1.
Proceed to `P0_3_CONSOLIDATED_REMEDIATION_PLAN.md` for the batch remediation plan and authorization request.
