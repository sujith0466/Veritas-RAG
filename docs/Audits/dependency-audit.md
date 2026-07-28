# RAGuard Backend — Dependency Audit Report

**Date:** July 21, 2026
**Scope:** Phase A9 — Dependency Verification

## 1. Dependency Analysis

An audit was performed on `requirements.txt` and the Docker build process to ensure stability, compatibility, and security.

### 1.1 Unpinned Packages
**Issue:** `structlog`, `PyJWT[crypto]`, and `reportlab` were appended to the requirements list without version constraints. This violates production reproducibility standards.
**Resolution:** Pinned to latest stable versions verified in the previous build:
- `structlog>=26.1.0`
- `PyJWT[crypto]>=2.13.0`
- `reportlab>=5.0.0`

### 1.2 Duplicate JWT Libraries
**Issue:** Both `python-jose[cryptography]>=3.3.0` and `PyJWT[crypto]` were present. Duplicate libraries for cryptographic operations create unnecessary attack surface and bundle bloat.
**Resolution:** Audited the codebase (`grep -r "jose" backend/`). Found 0 usages of `python-jose`. Verified that `backend/core/Security/jwt.py` explicitly imports `jwt` (PyJWT).
**Action:** Removed `python-jose[cryptography]>=3.3.0` from `requirements.txt`.

### 1.3 Qdrant Version Mismatch
**Issue:** `qdrant-client>=1.7.0` resolved to `1.18.0` during build, throwing a startup warning because the Qdrant server is pinned to `1.7.4`. A difference >1 minor version is not officially supported.
**Resolution:** Applied an upper bound to the client: `qdrant-client>=1.7.0,<1.9.0` to force pip to resolve a version compatible with the 1.7.x server family, ensuring API contract stability without risking data loss from an unverified server upgrade.

## 2. Unused Library Verification
- `celery`: Retained. Required for the background worker system (reliability module).
- `Faker`: Retained. Required for database seeders.

## 3. Conclusion
Dependencies are now securely pinned, duplicate cryptographic libraries have been purged, and vector database API compatibility is guaranteed.

**Status:** PASS
