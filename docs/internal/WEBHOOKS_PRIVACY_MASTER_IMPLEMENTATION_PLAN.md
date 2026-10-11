# Veritas-RAG — Webhooks & Privacy Master Implementation Plan

**Baseline Commit:** `0bf884302dbf7134ef4e3496245bc85b5e358b50`  
**Migration Head:** `wh_01_webhook_crypto`  
**Status:** IMPLEMENTED & LOCALLY CERTIFIED  
**Date:** 2026-10-11  

---

## 1. Scope & Execution Overview
Under Single Implementation Authorization, the modernization of `/settings/webhooks` and `/settings/privacy` has been executed across the following architectural work packages:
- **WP-0:** Repository preflight, schema audit, baseline protection.
- **WP-1:** Contract & threat model documentation (`docs/internal/WEBHOOKS_PRIVACY_MASTER_AUDIT.md`).
- **WP-2:** AES-256-GCM webhook secret encryption at rest, transparent migration fallback, Alembic migration `20261011_webhook_crypto.py`.
- **WP-3:** Webhook delivery logs API (`GET .../logs`), canonical event catalog (`GET .../events`), test ping dispatcher (`POST .../test`).
- **WP-4:** Webhook frontend modernization with authentic delivery logs table, event category selector, and HMAC test ping trigger.
- **WP-5:** Privacy data export engine (`DataExportService`), scrubbed JSON download endpoint (`POST /api/v1/users/me/export`).
- **WP-6:** Account lifecycle service (`UserLifecycleService`), password re-authentication, transactional sole-owner guard, soft-delete, Redis token blocklisting.
- **WP-7:** Privacy frontend modernization with real server-side export download and two-step password deactivation modal.
- **WP-8:** Automated test suites across backend (17/17 passing) and frontend (12/12 passing).
- **WP-9:** Local Docker rebuild and runtime verification of `api`, `worker`, and `frontend` services.
