# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0-milestone.7] - 2026-08-05
### Added
- **Epic 7 (Knowledge Base):** End-to-end workspace statistics and vector parity audits (F7.1), 4-dimensional mathematical Knowledge Health Scoring engine with coverage/freshness/quality/reliability dimensions (F7.2), exponential and linear Stale Document Detection decay evaluations with bulk archiving workflows (F7.3), and Zero-Downtime Blue/Green Vector Re-Indexing workflows supporting atomic Qdrant alias namespace swaps (F7.4).

## [2.0.0-milestone.6] - 2026-08-04
### Added
- **Epic 6 (Knowledge Processing Pipeline):** Asynchronous Celery + Redis worker queue topology with distributed locking and idempotency tokens (F6.1), OCR and multi-engine text extraction with Tesseract/EasyOCR fallback and extraction contract validation (F6.2), token-aware recursive text chunking and canonical manifest generation (F6.3), embedding generation worker with dimensional validation (F6.4), multi-tenant Qdrant vector indexing and payload enrichment (F6.5), ProcessingJob lifecycle tracking with granular step-level telemetry (F6.6), Dead Letter Queue engine with automated classification and retry remediation (F6.7), and S3 event-driven pipeline triggers with presigned upload lifecycle verification (F6.8).

## [2.0.0-milestone.5] - 2026-08-03
### Added
- **Epic 5 (Document & Folder Management):** Folder creation (adjacency list), hierarchical rename/soft delete, reparenting/moves, asynchronous permanent pruning, document archival/restoration, strict versioning (auto-increment and old vector cleanup), metadata management (key-value tagging with JSONB GIN index & Qdrant sync), and S3 presigned URL-based bulk uploads orchestrated by Celery workers.

## [2.0.0-milestone.4] - 2026-08-02
### Added
- **Epic 1 (Foundation):** SQLAlchemy 2.0 async engine, Redis connection manager & distributed locking, Qdrant vector client, S3 abstraction with WORM audit policies, OpenTelemetry observability, Prometheus metrics, and GitHub Actions CI/CD pipelines.
- **Epic 2 (Auth & Identity):** Server-side Argon2id auth, dual-token JWT + refresh rotation, Redis-backed active session management & instant revocation, cryptographic password reset, email verification, email OTP verification, and generic OAuth2/OIDC SSO provider framework.
- **Epic 3 (Workspace Governance):** Complete workspace provisioning lifecycle (`ACTIVE`, `ARCHIVED`, `SUSPENDED`, `SOFT_DELETED`), slug collision protection, JSON schema validated workspace settings with snapshot history & rollback, dynamic workspace branding compiler (CSS variables, Tailwind tokens, WCAG AA contrast validation), and Redis-backed 7-step feature flag evaluation engine with MurmurHash3 rollouts.
- **Epic 4 (User & Role Management):** RBAC permission matrix enforcement, role assignment/reassignment flows, workspace invitations with secure cryptographic tokens, user profile management, domain verification (DNS TXT based validation), and SSO configuration per workspace mapping Identity Providers.

### Changed
- Refactored frontend to support dynamic `BrandingProvider` (CSS root variables) and `FeatureFlagProvider` (`useFeatureFlag` hook & `<FeatureFlagGuard>` component).
- Upgraded backend endpoints to FastAPI v1 modular routing structure under `/api/v1/`.

## [1.0.0-rc1] - 2026-07-24
### Added
- Complete RAG pipeline with BM25 & Qdrant.
- Cross-Encoder Reranking and Confidence Engine.
- Multi-tenant architecture.
- Full UI for documents, chats, and chunking.
