# Veritas-RAG P0-3 — Migration Deployment-History Review & Multi-Defect Verification

**Document ID:** `P0_3_MIGRATION_DEPLOYMENT_HISTORY_REVIEW`  
**Date:** 2026-10-18  
**Scope:** Read-Only Audit of Deployment History, Alembic ScriptDirectory DAG, and Downstream Migration Chain  
**Status:** **MIGRATION REVIEW INCONCLUSIVE — DEPLOYMENT HISTORY UNKNOWN**

---

## 1. Executive Summary

This review investigates the deployment history of Alembic revisions `20260724_0224febbe7cc` and `20260815_6c11701a28c5`, verifies the two suspected schema defects, and identifies additional blockers along the migration path.

### Key Conclusions:
1. **Deployment History Verdict:**
   - **Revision `0224febbe7cc`:** Merged into `origin/main` and included in Git release tags `v1.0.0`, `v1.0.1`, and `v2.0-epic9-batch2-final`. Documented in `docs/Quality_Assurance/12_RELEASE_MANIFEST_v1.0.1.md`.
   - **Revision `6c11701a28c5`:** Merged into `origin/main` (commit `7952d68d069`), but untagged.
   - **Shared/Production Database Execution Status:** **UNKNOWN.** Repository CI/CD workflows (`deploy-staging.yml`, `release.yml`, `ci.yml`) do not execute Alembic migrations against remote databases (staging uses a placeholder hook; CI integration tests bypass Alembic via `BaseModel.metadata.create_all`). No remote deployment records exist locally.
2. **Defect 1 Verified (`0224febbe7cc` Line 67):**
   - Unconditionally attempts `op.drop_column('health_scan_jobs', 'is_deleted')`.
   - `health_scan_jobs` was created in `0008` without `is_deleted`, and no intervening migration or model ever added it. Fatal crash on fresh installations.
3. **Defect 2 Verified (`6c11701a28c5` Line 40):**
   - Unconditionally attempts `op.create_table('health_scan_jobs', ...)`.
   - Table `health_scan_jobs` already exists from `0008` and was never dropped or renamed.
4. **Additional Blockers Discovered in `6c11701a28c5` (13 Duplicate Table Collisions):**
   - Deep inspection of `6c11701a28c5` revealed that **13 other preexisting domain tables** are unconditionally recreated (`circuit_breaker_events`, `retrieval_sla_logs`, `document_chunks`, `chunk_relationships`, `embedding_jobs`, `chunk_embeddings`, `vector_index_metadata`, `stale_embedding_records`, `workspace_domains`, `domain_cooldowns`, `identity_providers`, `vector_reindex_jobs`).
   - If Defect 1 is resolved, migration execution on a fresh database crashes immediately at line 24 of `6c11701a28c5` on `relation "circuit_breaker_events" already exists`.
5. **Remediation Strategy:**
   - Because deployment status to live production databases is unknown, changing revision IDs or rewriting the DAG is ruled out.
   - The only safe strategy is **Idempotent / Defensive Guards**:
     - `0224febbe7cc`: `ALTER TABLE health_scan_jobs DROP COLUMN IF EXISTS is_deleted`
     - `6c11701a28c5`: Wrap duplicate `create_table` calls in `if not insp.has_table(...)` guards (matching existing repository precedent in `ws_b6_user_quotas_and_attribution.py`).

---

## 2. Task 1 — Verified Deployment-History Evidence & Remaining Unknowns

### 2.1 Git Metadata & Branch / Tag Analysis
Inspection of repository branches, remotes, and tags yielded the following facts:

- **Remotes:** `origin` points to `https://github.com/sujith0466/Veritas-RAG.git`.
- **Revision `0224febbe7cc`:**
  - Commit: `c6a5fe4e5bd5eb904b7df458f7a66144945a8692` (`chore: finalize RAGuard AI v1.0.1 production baseline`, 2026-07-28).
  - Branches: Present on `main` and `origin/main`.
  - Tags: Present in `v1.0.0`, `v1.0.1`, `v2.0-epic9-batch2-final`.
  - Documentation: Manifest `docs/Quality_Assurance/12_RELEASE_MANIFEST_v1.0.1.md` designates this commit as the "v1.0.1 Production Baseline".
- **Revision `6c11701a28c5`:**
  - Commit: `7952d68d069aacdf599402053ff0d2249a029da3` (`feat(notifications): complete Epic 11 Webhooks, Celery Delivery, and In-App Websockets`, 2026-08-15).
  - Branches: Present on `main` and `origin/main`.
  - Tags: Not present in any release tag.
  - Documentation: Referenced in `docs/internal/SETTINGS_MODERNIZATION_MASTER_AUDIT.md`.

### 2.2 CI/CD & Deployment Workflow Inspection
- `.github/workflows/deploy-staging.yml`:
  - Contains a placeholder hook:
    ```yaml
    - name: Placeholder Deployment Hook
      run: |
        echo "Triggering deployment for Staging Environment..."
        echo "(F1.8 Kubernetes IaC will replace this placeholder.)"
    ```
  - Does not execute database migrations or deploy infrastructure.
- `.github/workflows/release.yml`:
  - Triggers on tags `v*.*.*`.
  - Builds and pushes Docker images to `ghcr.io`.
  - Runs `pytest tests/ -v`, but does not run Alembic migrations.
- `.github/workflows/ci.yml`:
  - Starts Postgres 15 and Redis 7 Alpine containers for integration testing.
  - Test setup (`tests/integration/conftest.py` line 20) runs `await conn.run_sync(BaseModel.metadata.create_all)`, completely bypassing Alembic migrations.
- `scripts/migrate.sh`:
  - Contains `alembic upgrade head`, but is not invoked by any automated CI/CD pipeline.

### 2.3 Verified Facts vs. Remaining Unknowns

| Category | Verified Evidence | Remaining Unknowns |
|---|---|---|
| **Git Lineage** | Both commits are in `origin/main`. `0224febbe7cc` is tagged in `v1.0.1`. | None regarding Git history. |
| **Release Artifacts** | Docker images were published for `v1.0.1` and `staging`. | Whether images were pulled/run in production. |
| **Live Database State** | E2E test database is fresh and fails at `0224febbe7cc`. | **UNKNOWN** whether any external production/staging database has executed `0224febbe7cc` or `6c11701a28c5`, was stamped (`alembic stamp`), or was created via `BaseModel.metadata.create_all`. |

---

## 3. Task 2 — Alembic Graph Ancestry & Multi-Defect Verification

### 3.1 Offline Revision Graph Verification
Verified via `alembic.script.ScriptDirectory` (offline API, independent of text searches):
- **Base:** Exactly one root: `0001` (`0001_initial_schema.py`).
- **Head:** Exactly one head: `wh_01_webhook_crypto` (`20261011_webhook_crypto.py`).
- **Total Revisions:** 68 files.
- **Topological Traversal:**
  - `0224febbe7cc` is at traversal index 22 from base.
  - `6c11701a28c5` is at traversal index 50 from base.
  - `0224febbe7cc` is confirmed to be an unconditional ancestor of `6c11701a28c5`.
  - Any fresh database migration running `alembic upgrade head` must execute `0224febbe7cc` before reaching `6c11701a28c5`.

### 3.2 Verification of Suspected Defect 1 (`0224febbe7cc`)
- **Failing Operation:** Line 67: `op.drop_column('health_scan_jobs', 'is_deleted')`.
- **Table Origin:** Created in `0008_knowledge_health_schema.py` (lines 25–49) with 12 columns (`id`, `tenant_id`, `scan_type`, `status`, `orphans_found`, `orphans_purged`, `stale_chunks_found`, `parity_status`, `duration_ms`, `error_message`, `created_at`, `updated_at`). **No `is_deleted` column.**
- **Intervening History:** Revisions `0009` through `0021` and `680b30cdb5dd` never add `is_deleted`.
- **Model Check:** `HealthScanJob` (`backend/modules/knowledge_health/models/health_scan.py`) inherits from `Base` and has no `is_deleted` field.
- **Conditions/Guards:** None. The call is a bare `op.drop_column`.
- **Verdict:** **Confirmed Defect.** Deterministic failure on all fresh databases.

### 3.3 Verification of Suspected Defect 2 (`6c11701a28c5`)
- **Suspected Operation:** Line 40: `op.create_table('health_scan_jobs', ...)`.
- **Table State at Revision 50:** Table `health_scan_jobs` was created in `0008` (Revision 8). No migration between `0008` and `6c11701a28c5` ever dropped or renamed `health_scan_jobs`.
- **Conditions/Guards:** None. Unconditional `op.create_table`.
- **Verdict:** **Confirmed Defect.** Would immediately fail with `relation "health_scan_jobs" already exists`.

### 3.4 Discovery of Additional Blockers (13 Duplicate Table Collisions in `6c11701a28c5`)
A full AST audit of `6c11701a28c5` revealed that the author autogenerated table creations for **14 tables**, of which **13 already exist**:

```
Migration 6c11701a28c5 Table Audit:
  1. circuit_breaker_events  --> Already created in 0007 (FATAL COLLISION at line 24)
  2. health_scan_jobs        --> Already created in 0008 (FATAL COLLISION at line 40)
  3. notification_delivery_logs --> GENUINE NEW TABLE (Intended for Epic 11)
  4. retrieval_sla_logs      --> Already created in 0007 (FATAL COLLISION)
  5. vector_reindex_jobs     --> Already created in 20260805095756 (FATAL COLLISION)
  6. workspace_webhooks      --> GENUINE NEW TABLE (Intended for Epic 11)
  7. domain_cooldowns        --> Already created in c722fc06aec0 (FATAL COLLISION)
  8. identity_providers      --> Already created in c722fc06aec0 (FATAL COLLISION)
  9. workspace_domains       --> Already created in c722fc06aec0 (FATAL COLLISION)
 10. document_chunks         --> Already created in 0003 (FATAL COLLISION)
 11. embedding_jobs          --> Already created in 0004 (FATAL COLLISION)
 12. vector_index_metadata   --> Already created in 0005 (FATAL COLLISION)
 13. chunk_embeddings        --> Already created in 0004 (FATAL COLLISION)
 14. chunk_relationships     --> Already created in 0003 (FATAL COLLISION)
 15. stale_embedding_records --> Already created in 0008 (FATAL COLLISION)
```

**Significance:** Fixing Defect 1 alone will NOT allow migrations to succeed on a fresh database. Alembic will crash on line 24 of `6c11701a28c5` when attempting to create `circuit_breaker_events`.

---

## 4. Task 3 — Remediation Strategy Evaluation & Recommendation

### 4.1 Evaluation of Remediation Approaches

| Dimension | Option A: Correct Historical Operations In-Place (Surgical Removal) | Option B: Add New Corrective Migration at HEAD | Option C: Conditional / Idempotent Guards (Recommended) |
|---|---|---|---|
| **Fresh Database** | Succeeded (clean DDL). | **FAILED.** Cannot fix historical crash; halts at rev 22. | **Succeeded.** Idempotent execution skips missing/duplicate operations. |
| **Existing Database** | Unaffected (revision IDs unchanged). | Applies at end of chain. | **Unaffected & Safe.** Handles both presence and absence of columns/tables. |
| **Deployment Uncertainty Risk** | Low (if rev was already applied, Alembic skips it). | High (does not resolve fresh DB setup). | **ZERO RISK.** Functions identically regardless of live DB status. |
| **Schema Drift & Data Loss** | Restores true baseline intent. | Retains corrupt autogen history. | Neutralizes drift without data loss. |
| **Precedent in Repo** | None. | Standard Alembic pattern. | **Direct Precedent:** `20261005_ws_b6_user_quotas_and_attribution.py` uses `inspect(op.get_bind())` and `if not insp.has_table(...)`. |

### 4.2 How Unknown Deployment Status Governs the Decision
Because it is **unknown** whether an external shared/production database is stamped at `0224febbe7cc` or `6c11701a28c5`:
- **We MUST NOT alter revision IDs or down_revision pointers.** Doing so would cause `alembic_version` mismatch errors on any database where these revisions were already stamped.
- **We MUST NOT rely on operations being present or absent.**
- **We MUST use idempotent operations:**
  - `ALTER TABLE health_scan_jobs DROP COLUMN IF EXISTS is_deleted;` safely executes whether or not the column exists.
  - `if not insp.has_table("<table_name>"): op.create_table(...)` safely creates tables on fresh databases without colliding on existing databases.

---

## 5. Ranked Remediation Recommendation

### Rank 1 (Recommended): Idempotent In-Place Hardening
Apply safe, defensive execution to the two affected migrations while preserving revision IDs and migration graph topology:

1. **In `20260724_0224febbe7cc_add_relative_path_to_document.py`:**
   Replace line 67:
   ```python
   # From:
   op.drop_column('health_scan_jobs', 'is_deleted')

   # To:
   op.execute("ALTER TABLE health_scan_jobs DROP COLUMN IF EXISTS is_deleted")
   ```
2. **In `20260815_6c11701a28c5_epic11_notifications.py`:**
   Wrap the 13 duplicate table creations in defensive `if not insp.has_table(...)` guards using `sa.inspect(op.get_bind())`, exactly as implemented in `ws_b6_user_quotas_and_attribution.py`.

### Explicit Approvals Required Before Implementation:
1. Approval to edit `backend/database/migrations/versions/20260724_0224febbe7cc_add_relative_path_to_document.py`.
2. Approval to edit `backend/database/migrations/versions/20260815_6c11701a28c5_epic11_notifications.py`.
3. Approval to execute an isolated offline test migration on a temporary PostgreSQL container to prove migration from `0001` to `HEAD`.

---

## 6. Audit Confirmation

Throughout this review:
- **Zero databases were altered or connected to.**
- **Zero migrations were edited, renamed, deleted, or executed.**
- **Zero application code, tests, or configuration files were changed.**
- **All 20 tracked modified files remain preserved at the preflight baseline.**

---

MIGRATION REVIEW INCONCLUSIVE — DEPLOYMENT HISTORY UNKNOWN
