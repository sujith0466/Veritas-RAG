# Veritas-RAG — Webhooks & Privacy Master Audit & Threat Model

**Baseline Commit:** `0bf884302dbf7134ef4e3496245bc85b5e358b50`  
**Audit Date:** 2026-10-11  

---

## 1. Webhooks Architecture Forensic Audit

### 1.1 Secret Storage
- **Observed State:** In `backend/services/workspace_webhooks.py`, `create_webhook` generated a random 32-byte secret using `secrets.token_urlsafe(32)` and assigned it directly to `WorkspaceWebhook.secret_hash`.
- **Finding:** Despite the column name `secret_hash`, the value stored was plaintext. This was done so `backend/tasks/webhooks.py` could read the raw secret to compute HMAC-SHA256 signatures (`hmac.new(secret, canonical_body, hashlib.sha256)`).
- **Vulnerability:** Critical Plaintext Credential Exposure at rest in PostgreSQL.
- **Remediation:** Introduce AES-256-GCM authenticated symmetric encryption with key derivation from `WEBHOOK_ENCRYPTION_KEY` (falling back to derived HKDF key from `APP_SECRET_KEY`). Add `encrypted_secret` column. Support zero-downtime migration fallback.

### 1.2 SSRF Architecture
- **Observed State:** `WorkspaceWebhookService._resolve_and_validate_url` performs HTTPS enforcement and DNS resolution via `socket.getaddrinfo`, checking for `ip.is_private`, `is_loopback`, `is_link_local`, `is_multicast`, and `169.254.169.254`.
- **Finding:** The worker (`tasks/webhooks.py`) re-invoked `_resolve_and_validate_url` before dispatch, but used standard `httpx.AsyncClient` without pinning the resolved IP or defending against DNS rebinding / malicious redirect chains.
- **Remediation:** Enhance `_resolve_and_validate_url` to reject IPv4-mapped IPv6, mixed DNS answers, and enforce `follow_redirects=False` in `httpx` so redirects cannot bypass SSRF validation.

### 1.3 Event Catalog & Dispatching
- **Observed State:** 40+ canonical events defined in `backend/core/events/types.py`. Frontend hardcoded `events: ['*']`.
- **Remediation:** Expose `GET /workspaces/{tenant_id}/webhooks/events` returning categorized canonical event definitions. Group into:
  1. Document Lifecycle (`document.uploaded`, `document.processed`, `document.failed`, etc.)
  2. Workspace & Members (`workspace.invitation_created`, `workspace.member_removed`, etc.)
  3. Reliability & Knowledge Health (`reliability.score_updated`, `alert.triggered`, etc.)
  4. System & Security (`user.profile_updated`, `feature_flag.updated`, etc.)

---

## 2. Privacy & Data Governance Forensic Audit

### 2.1 Data Export
- **Observed State:** `frontend/src/pages/settings/PrivacySettings.tsx` invoked `setTimeout(1500)` and serialized the client Zustand `user` state into a JSON blob.
- **Finding:** Complete simulation. Missing server-side data extraction, audit logging, and sensitive field filtering.
- **Remediation:** Implement server-side `DataExportService` and `POST /api/v1/users/me/export` returning profile, preferences, workspace memberships, and recent notification logs while strictly excluding hashes, salts, and secrets.

### 2.2 Account Lifecycle & Deactivation
- **Observed State:** `PrivacySettings.tsx` invoked `setTimeout(1000)` and displayed a warning toast ("Action Restricted").
- **Finding:** No backend route or service existed for user deactivation or account deletion.
- **Remediation:** Implement `POST /api/v1/users/me/deactivate` requiring password re-authentication, transactional sole-owner workspace checks, soft-delete (`is_deleted=True, is_active=False`), Redis token revocation, and user session revocation.
