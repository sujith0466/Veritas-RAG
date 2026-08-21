# EPIC-15 INFRASTRUCTURE-GATED CERTIFICATION CLOSURE PLAN

**Program**: RAGuard V2 Multi-Tenant Enterprise AI Platform
**Epic**: Epic-15 — Production Hardening & Enterprise Security
**Document Type**: Engineering Execution & Gate-Closure Plan
**Authoritative Evidence Baseline**: [`docs/internal/EPIC_15_LIVE_VALIDATION_REPORT.md`](file:///d:/RAGuard/docs/internal/EPIC_15_LIVE_VALIDATION_REPORT.md)
**Current Baseline**: Epics 1–14 Certified & Frozen (87.50%) | Epic 15 at 0.00%
**Status**: 📋 AWAITING INFRASTRUCTURE PROVISIONING & HUMAN EXECUTION AUTHORIZATION

---

## 1. Baseline State & Accepted Evidence Confirmation

The following feature statuses are accepted as the authoritative project baseline:

- **F15.1 (Third-Party Penetration Test)**: `READY — EXTERNAL VENDOR REQUIRED`
- **F15.2 (Load Testing)**: `PASS — LOCAL RUNTIME VALIDATED (ATOMIC QUOTA)` (k6 multi-scenario staging execution pending).
- **F15.3 (Chaos Engineering)**: `PASS — AUTOMATED VALIDATION` (Live Kubernetes staging chaos drills pending).
- **F15.4 (Disaster Recovery)**: `BLOCKED — CROSS-REGION INFRASTRUCTURE REQUIRED`
- **F15.5 (Backup Restoration)**: `PASS — AUTOMATED/SCRIPT VALIDATION` (Live Kubernetes staging backup restoration pending).
- **F15.6 (Security Headers)**: `PASS — LOCAL ASGI VALIDATION` (Live Nginx/Ingress edge scan pending).
- **F15.7 (Audit Log WORM)**: `PASS — CRYPTOGRAPHIC WORM VALIDATED` (Physical S3/MinIO Object Lock validation pending).
- **F15.8 (Runbook Finalization)**: `PASS — DOCUMENTATION & IMPLEMENTATION VALIDATED`

---

## 2. Required External Infrastructure & Procurement Gates

To close the remaining gates and achieve 100% certification for Epic 15, the following 4 infrastructure components must be provisioned:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL GATING PREREQUISITES                     │
├────────────────────────────────┬───────────────────────────────────────┤
│ 1. Kubernetes Staging Cluster  │ EKS / GKE / On-Prem v1.28+ with        │
│    (Target: raguard-staging)   │ Nginx Ingress Controller & cert-manager│
├────────────────────────────────┼───────────────────────────────────────┤
│ 2. Secondary Cloud Region      │ Cold standby VPC in alternate region   │
│    (Target: raguard-dr-standby)│ with storage mirror for cross-region DR│
├────────────────────────────────┼───────────────────────────────────────┤
│ 3. WORM S3 Storage Bucket      │ AWS S3 / MinIO with Object Locking     │
│    (Target: audit-archives)    │ enabled in Compliance Mode             │
├────────────────────────────────┼───────────────────────────────────────┤
│ 4. External Security Firm      │ Accredited CREST / SOC2 third-party    │
│    (Target: Vendor Engagement) │ penetration testing firm               │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 3. Feature-by-Feature Gate Closure Plan

### Gate Closure 1: F15.6 — Live Staging Edge Ingress & TLS Scan
* **Prerequisite**: Staging cluster deployed with ingress controller and DNS mapped to `staging.raguard.ai`.
* **Execution Procedure**:
  ```bash
  # Probe edge endpoint from external network
  curl -I https://staging.raguard.ai/api/v1/auth/login
  ```
* **Required Evidence**:
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none';`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
  - `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 0`
  - Valid TLS certificate issued by Let's Encrypt / DigiCert.
* **Exit Criteria**: Live curl HTTP header capture logged with 100% security header compliance $\to$ **`F15.6 CERTIFIED`**.

---

### Gate Closure 2: F15.2 — k6 Multi-VU Staging Load Execution
* **Prerequisite**: Staging API reachable at `BASE_URL=https://staging.raguard.ai`, test tenant seeded (`00000000-0000-0000-0000-000000000001`).
* **Execution Procedure**:
  ```bash
  BASE_URL="https://staging.raguard.ai" bash k6/run_all.sh
  ```
  Runs all 6 scenarios:
  1. `auth_workload.js` (100 VUs, 5 mins)
  2. `concurrent_users.js` (100 VUs, 5 mins)
  3. `chat_streaming.js` (50 SSE connections, 5 mins)
  4. `document_upload.js` (50 VUs, 3 mins)
  5. `quota_concurrent_increment.js` (100 concurrent atomic increments)
  6. `mixed_enterprise_workload.js` (85 VUs blended, 10 mins)
* **Required Evidence**:
  - HTTP 5xx error rate $< 1.0\%$.
  - Auth P95 $< 400\text{ms}$, Chat first-token P95 $< 3.0\text{s}$, Upload P95 $< 5.0\text{s}$.
  - Quota mathematical conservation verified: $\text{Final} \equiv \text{Initial} + (\text{Tokens/Req} \times \text{Successes})$.
* **Exit Criteria**: k6 CLI summary JSON reports and Grafana saturation logs archived $\to$ **`F15.2 CERTIFIED`**.

---

### Gate Closure 3: F15.3 — Live Kubernetes Chaos Engineering Drills
* **Prerequisite**: ServiceAccount `raguard-chaos-runner` active in namespace `raguard-staging`.
* **Execution Procedure**:
  Execute documented C1–C8 chaos matrix during sustained background traffic:
  - **C1 (API Pod Crash)**: `kubectl delete pod -n raguard-staging -l app.kubernetes.io/name=raguard`
  - **C2 (Redis Drop)**: Scale Redis deployment to 0 replicas; verify `QuotaGovernor` falls back to PostgreSQL.
  - **C3 (Database Saturation)**: Inject connection limits; verify pool exhaustion queuing and circuit breaking.
  - **C4 (Qdrant Disconnect)**: Inject header `x-raguard-chaos-token: test-qdrant-drop`; verify circuit breaker moves `CLOSED \to OPEN`.
  - **C5 (Object Storage Outage)**: Stop MinIO container; verify upload isolation.
  - **C6 (Worker Termination)**: Kill Celery worker; verify task redelivery via RabbitMQ/Redis DLQ.
  - **C7 / C8 (LLM Provider Failover)**: Inject header `x-raguard-chaos-token: test-llm-outage`; verify failover to secondary provider.
* **Required Evidence**:
  - Zero data corruption or cross-tenant leakage.
  - Automatic recovery within $\le 30\text{ seconds}$ post-fault resolution.
  - Prometheus alert firing and resolution logs recorded.
* **Exit Criteria**: Chaos execution log signed by Lead SRE $\to$ **`F15.3 CERTIFIED`**.

---

### Gate Closure 4: F15.5 — Live Staging Backup Restoration Drill
* **Prerequisite**: Backup CronJob executed and backup artifact present in `postgres-backup-pvc`.
* **Execution Procedure**:
  ```bash
  # 1. Trigger manual backup
  kubectl create job --from=cronjob/postgres-backup manual-pre-restore-backup -n raguard-staging
  kubectl wait --for=condition=complete job/manual-pre-restore-backup -n raguard-staging --timeout=120s

  # 2. Execute restore script against staging target
  bash infrastructure/scripts/dr/restore_postgres.sh /backup/db_staging_latest.sql --confirm
  ```
* **Required Evidence**:
  - Schema restored with non-zero table count.
  - Seed workspace `00000000-0000-0000-0000-000000000001` intact.
  - Application `/health/ready` returns HTTP 200 post-restore.
* **Exit Criteria**: Timed restoration log recorded with database integrity checksum $\to$ **`F15.5 CERTIFIED`**.

---

### Gate Closure 5: F15.7 — Physical S3 / MinIO Object Lock Compliance Validation
* **Prerequisite**: Staging MinIO or AWS S3 bucket provisioned with Object Locking enabled.
* **Execution Procedure**:
  ```bash
  # 1. Set Compliance mode retention (1 year)
  mc retention set --default COMPLIANCE 365d staging/audit-archives

  # 2. Upload signed WORM audit archive package
  mc cp /tmp/audit_archive_202608.json staging/audit-archives/tenant-01/

  # 3. Attempt unauthorized deletion
  mc rm staging/audit-archives/tenant-01/audit_archive_202608.json
  ```
* **Required Evidence**:
  - S3 / MinIO returns `AccessDenied` error: `[AccessDenied] Object under active WORM compliance retention cannot be deleted`.
* **Exit Criteria**: Physical S3 response transcript archived $\to$ **`F15.7 CERTIFIED`**.

---

### Gate Closure 6: F15.4 — Physical Cross-Region Disaster Recovery Drill
* **Prerequisite**: Cold standby cluster provisioned in secondary cloud region.
* **Execution Procedure**:
  1. Simulate primary region catastrophic outage (cut ingress routing).
  2. Sync latest backup dump and Qdrant snapshots to secondary region.
  3. Execute `restore_postgres.sh` and `restore_qdrant.sh` in secondary region.
  4. Cold-start backend API and Celery workers.
  5. Run `verify_restore.sh https://standby.raguard.ai`.
  6. Measure total elapsed time ($T_{\text{start}} \to T_{\text{ready}}$).
* **Required Evidence**:
  - Measured Recovery Time Objective: $\text{RTO} \le 1.0\text{ hour}$.
  - Measured Recovery Point Objective: $\text{RPO} \le 24.0\text{ hours}$.
  - Verification probes return HTTP 200 green across all datastores.
* **Exit Criteria**: Formal Disaster Recovery Drill Post-Mortem Report $\to$ **`F15.4 CERTIFIED`**.

---

### Gate Closure 7: F15.1 — Third-Party Penetration Test Execution & Retest
* **Prerequisite**: External security firm contracted; staging environment provisioned with test credentials.
* **Execution Procedure**:
  1. Hand off [`docs/Security/PENTEST_SCOPE.md`](file:///d:/RAGuard/docs/Security/PENTEST_SCOPE.md) to vendor.
  2. Vendor executes 2-week white/gray/black box assessment.
  3. Engineering remediates any discovered findings.
  4. Vendor executes retest and validates remediations.
* **Required Evidence**:
  - Vendor-signed Penetration Testing Final Report.
  - Formal Executive Summary confirming: **0 Critical, 0 High unresolved findings**.
  - Vendor Retest Confirmation Letter.
* **Exit Criteria**: Signed vendor report archived in `docs/Security/evidence/` $\to$ **`F15.1 CERTIFIED`**.

---

## 4. Phased Closure Execution Roadmap

```
Phase 1: Staging Infrastructure Setup
    ├── 1.1: Deploy Kubernetes staging manifests (raguard-staging)
    ├── 1.2: Verify staging ingress, TLS, and security headers (F15.6)
    └── 1.3: Enable S3 Object Locking in Compliance Mode (F15.7)

Phase 2: Performance & Resilience Drills
    ├── 2.1: Execute k6 multi-VU load suite & quota stress test (F15.2)
    └── 2.2: Execute live Kubernetes C1–C8 chaos experiments (F15.3)

Phase 3: Disaster Recovery & Restoration Drills
    ├── 3.1: Execute staging backup and database restore drill (F15.5)
    └── 3.2: Execute cross-region cold standby recovery drill & RTO/RPO timing (F15.4)

Phase 4: External Vendor Engagement & Final Sign-Off
    ├── 4.1: Vendor executes external penetration test (F15.1)
    ├── 4.2: Remediate findings & obtain vendor sign-off letter (F15.1)
    └── 4.3: Final human review -> Update Master Trackers to 93.75% (Epic 15 Frozen)
```

---

## 5. Final Certification Sign-off Criteria (Master Tracker Gate)

The Program 2 Master Trackers (`docs/internal/PROGRAM_2_MASTER_TRACKER.md` and `raguard_v2_program2_master_tracker.md`) will be updated from **87.50% (14/16 Epics)** to **93.75% (15/16 Epics)** and Epic-15 marked **COMPLETED / CERTIFIED / FROZEN** only when:

1. [ ] F15.6: Staging edge TLS and security header response transcript archived.
2. [ ] F15.2: k6 multi-scenario staging JSON report archived with passing SLOs.
3. [ ] F15.3: Staging chaos engineering drill report signed by Lead SRE.
4. [ ] F15.5: Staging backup restoration drill post-mortem signed.
5. [ ] F15.7: Physical S3 Object Lock compliance retention response transcript archived.
6. [ ] F15.4: Cross-region DR drill post-mortem verifying RTO $\le 1\text{hr}$ / RPO $\le 24\text{hrs}$ signed.
7. [ ] F15.1: Third-party vendor penetration test signed report archived with 0 Critical / 0 High findings.
8. [ ] Full project regression suite (126+ tests) passes with 100% success rate.
9. [ ] Formal CTO / Human Lead approval granted.
