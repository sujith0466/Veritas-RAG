# Veritas-RAG — Webhooks & Privacy Modernization: Master Implementation Tracker

**Baseline Commit:** `0bf884302dbf7134ef4e3496245bc85b5e358b50`  
**Branch:** `main`  
**Authorization Mode:** Single End-to-End Implementation Authorization  
**Current Date:** 2026-10-11  

---

## 1. Work Package Execution Status

| Work Package | Title | Status | Primary Artifacts / Changes | Evidence & Notes |
| :--- | :--- | :--- | :--- | :--- |
| **WP-0** | Preflight and Repository Protections | **Passed** | Git preflight, schema audit, vitest preflight | Git `0bf8843`, uncommitted files preserved, Alembic head `notif_01_in_app_notifications`, 9 containers healthy, vitest 10/10 passed. |
| **WP-1** | Contract & Threat-Model Validation | **Passed** | `docs/internal/WEBHOOKS_PRIVACY_MASTER_AUDIT.md`, `WEBHOOKS_PRIVACY_MASTER_TRACKER.md` | Audit document completed, AES-GCM crypto selected, canonical events mapped from `backend/core/events/types.py`. |
| **WP-2** | Webhook Encryption & Migration | **In Progress** | `backend/core/security/webhook_crypto.py`, migration `20261011_webhook_crypto_and_user_lifecycle.py`, entity & service updates | Adding `encrypted_secret` column to `workspace_webhooks`, AES-256-GCM symmetric encryption using `WEBHOOK_ENCRYPTION_KEY` / `APP_SECRET_KEY`. |
| **WP-3** | Webhook APIs | **Not Started** | `backend/api/v1/routes/workspace_webhooks.py`, `backend/schemas/workspace_webhook.py` | Add `/logs`, `/test`, `/events` endpoints with strict tenant scoping. |
| **WP-4** | Webhook Frontend Modernization | **Not Started** | `frontend/src/pages/settings/WebhookSettings.tsx`, `frontend/src/api/webhooks.ts` | Delivery logs drawer, categorized event tree selector, test ping dispatch. |
| **WP-5** | Privacy Export Backend | **Not Started** | `backend/services/user_export.py`, `POST /api/v1/users/me/export` | Aggregate profile, memberships, preferences, audit events; scrub all secrets/hashes/salts. |
| **WP-6** | Account Lifecycle Backend | **Not Started** | `backend/services/user_lifecycle.py`, `POST /api/v1/users/me/deactivate` | Password re-auth, transactional sole-owner guard, soft-delete, Redis session revocation. |
| **WP-7** | Privacy Frontend Modernization | **Not Started** | `frontend/src/pages/settings/PrivacySettings.tsx`, `frontend/src/api/privacy.ts` | Real export download, two-step password & "DELETE" confirmation modal. |
| **WP-8** | Security & Automated Regression Tests | **Not Started** | Unit & integration tests for crypto, logs, export scrubber, sole-owner lock | Use dedicated disposable test identities; strictly never touch demo accounts. |
| **WP-9** | Local Runtime Verification & Final Reporting | **Not Started** | Container rebuild, end-to-end verification report | Verification across API, Worker, and Frontend containers. |

---

## 2. Requirement Verification Matrix

| Req ID | Domain | Requirement Description | Verification Method | Status |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-WH-1** | Webhooks | AES-256-GCM authenticated secret encryption at rest | Unit test round-trip + tampering | Not Started |
| **REQ-WH-2** | Webhooks | Secret migration fallback & zero-loss compatibility | Migration test with existing records | Not Started |
| **REQ-WH-3** | Webhooks | Pre-dispatch and connection-time SSRF defenses | Unit tests blocking private/loopback/cloud metadata | Not Started |
| **REQ-WH-4** | Webhooks | Workspace-authorized, paginated delivery logs API | Integration test with tenant isolation check | Not Started |
| **REQ-WH-5** | Webhooks | Ad-hoc test webhook dispatch via Celery & HMAC signing | Worker execution log + test event | Not Started |
| **REQ-WH-6** | Webhooks | Canonical event catalog & categorized selection UI | Unit test on canonical events + Frontend vitest | Not Started |
| **REQ-PR-1** | Privacy | Server-side data export API (`POST /me/export`) | Schema verification + scrubbing test | Not Started |
| **REQ-PR-2** | Privacy | Zero credential / secret exposure in export bundle | Assertion on forbidden keys in export JSON | Not Started |
| **REQ-PR-3** | Privacy | Mandatory password re-authentication for deactivation | Integration test with valid vs invalid passwords | Not Started |
| **REQ-PR-4** | Privacy | Transactional sole-owner workspace deactivation guard | Integration test on sole owner vs multi-owner | Not Started |
| **REQ-PR-5** | Privacy | Full session revocation across Redis & DB on deactivation | Check token blocklist & UserSession invalidation | Not Started |
| **REQ-PR-6** | Privacy | Authentic frontend UX (no `setTimeout` simulations) | Component vitests verifying authentic API calls | Not Started |
