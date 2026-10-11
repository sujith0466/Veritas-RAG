# Veritas-RAG — Webhooks & Privacy Acceptance Matrix

**Audit Baseline:** `0bf884302dbf7134ef4e3496245bc85b5e358b50`  
**Migration Head:** `wh_01_webhook_crypto`  
**Certification Date:** 2026-10-11  

---

| ID | Domain | Requirement & Acceptance Criteria | Verification Method | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AC-WH-1** | Webhooks | AES-256-GCM encrypted secret at rest with unique nonce and HMAC signing compatibility | Unit tests + DB schema inspection | **PASS** | `test_webhook_crypto.py` (5/5 pass), `encrypted_secret` column added in Postgres |
| **AC-WH-2** | Webhooks | Zero-loss legacy migration fallback for existing plaintext secrets | Unit test `test_get_delivery_secret_legacy_and_encrypted` | **PASS** | Transparently upgrades legacy secret to encrypted token upon retrieval |
| **AC-WH-3** | Webhooks | SSRF protection rejects private IP, loopback, multicast, cloud metadata, and redirects | Unit tests `test_workspace_webhooks.py` + `httpx` config | **PASS** | `_resolve_and_validate_url` verified (5/5 pass); `follow_redirects=False` enforced |
| **AC-WH-4** | Webhooks | Paginated, workspace-authorized delivery logs API (`GET .../logs`) | Integration unit tests + OpenAPI spec | **PASS** | Bounded pagination, sensitive credentials omitted, tenant-scoped |
| **AC-WH-5** | Webhooks | Ad-hoc test webhook dispatch via Celery worker (`POST .../test`) | Route check + OpenAPI registration | **PASS** | Queues `test.ping` via Celery task, logged to `notification_delivery_logs` |
| **AC-WH-6** | Webhooks | Canonical domain event catalog (`GET .../events`) & Categorized UI | Vitest + Backend route | **PASS** | Canonical EventType enumeration grouped into 5 categories |
| **AC-PR-1** | Privacy | Server-side data export API (`POST /api/v1/users/me/export`) | Unit test `test_scrub_dict_removes_sensitive_keys` | **PASS** | Compiles profile, preferences, memberships, notifications |
| **AC-PR-2** | Privacy | Forbidden credential exclusion in export payload | Unit test assertion on `FORBIDDEN_EXPORT_KEYS` | **PASS** | Zero password hashes, salts, reset tokens, or API secrets exported |
| **AC-PR-3** | Privacy | Mandatory password re-authentication for deactivation | Unit test `test_user_lifecycle_reauthentication_failure` | **PASS** | Rejects invalid credentials; allows verified passwords |
| **AC-PR-4** | Privacy | Transactional sole-owner workspace deactivation guard | Unit test + service logic | **PASS** | Fails with `SoleWorkspaceOwnerConflictException` if user is sole owner of active workspace |
| **AC-PR-5** | Privacy | Session revocation across database and Redis | JWTService `revoke_user_tokens` + DB update | **PASS** | `UserSession.is_revoked = True` + Redis `auth:user:{id}:invalid_before` blocklist |
| **AC-PR-6** | Privacy | Authentic frontend UX (no `setTimeout` mock simulations) | Vitest `webhooksAndPrivacy.test.tsx` + Frontend build | **PASS** | Production build passes; real fetch calls trigger server downloads and deactivation modal |
