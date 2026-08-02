# F1.5 Baseline Audit and Gap Analysis (Object Storage Foundation)

## Executive Summary
A comprehensive read-only audit of the RAGuard Version 1 codebase was conducted to evaluate object storage capabilities. The V1 baseline introduces an exceptionally robust storage abstraction (`backend/document/storage/base.py`) and a rigorous verification contract (`CONTRACT_001`). However, cloud providers (like S3) are currently stubbed, telemetry is missing, and an architectural duplication exists within a secondary storage module.

## 1. Audit Findings

### 1.1 Core Abstractions (`backend/document/storage/base.py`)
- **Current State:** Defines `StorageProvider`, `StorageObjectDTO`, and standardizes `get_versioned_path()`. 
- **Assessment:** High-quality enterprise design. Isolates byte-streaming from JSON serialization perfectly.

### 1.2 Local Implementation (`backend/document/storage/local.py`)
- **Current State:** Fully implements `LocalStorageProvider`, securely restricting path traversal (`STORE_001`) and computing SHA-256 checksums on the fly.
- **Assessment:** Ready for reuse in local development scenarios.

### 1.3 Cloud Implementations (`backend/document/storage/cloud.py`)
- **Current State:** Contains stub classes (`S3StorageProvider`, `AzureBlobStorageProvider`) which raise `NotImplementedError`.
- **Assessment:** Incomplete. Requires full implementation using an async S3 client (e.g., `aioboto3`).

### 1.4 Architectural Duplication (`backend/modules/storage/services/provider.py`)
- **Current State:** A completely separate `StorageProvider` exists here containing `upload_file()` for avatars, which is injected via `backend/core/dependencies/storage.py`.
- **Assessment:** Architectural smell. RAGuard must have a single `StorageProvider` abstraction. This duplicate must be replaced.

### 1.5 Missing Capabilities
- **MinIO Emulation:** `docker-compose.yml` lacks a local object storage emulator.
- **Object Lock / WORM:** No infrastructure exists to enforce Write-Once-Read-Many (WORM) policies on `audit_logs/`.
- **Pre-signed URLs:** No native interface for generating temporary UI download links.
- **Observability:** No `StorageMetrics` exist.

---

## 2. Gap Analysis

| Component | Class | Current State | Required State | Recommendation | Target Task |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Object Storage Abstraction** | ✅ Reuse As-Is | Robust binary I/O interface. | Add `get_presigned_url()`. | Extend `StorageProvider` interface. | Task 1 |
| **Local Storage** | ✅ Reuse As-Is | Secure volume handling. | Support `get_presigned_url` (mocked). | Keep as-is, minor extension. | Task 1 |
| **S3 Storage Client** | 🆕 Implement New | Stubbed in `cloud.py`. | Full asynchronous I/O. | Implement `S3StorageProvider` using `aioboto3`. | Task 2 |
| **Resilience & Retries** | ⬆ Improve | None. | `with_retry` protection. | Wrap S3 network ops in `with_retry`. | Task 2 |
| **Architectural Duplication** | 🔴 Replace | `modules/storage/...` duplicates interface. | Single abstraction. | Delete duplicate, redirect dependencies. | Task 3 |
| **Bucket Lifecycle & WORM** | 🆕 Implement New | None. | Provision bucket with Object Lock. | Create init utility for buckets & WORM. | Task 4 |
| **Storage Metrics** | 🆕 Implement New | None. | Track bandwidth and latency. | Create `StorageMetrics` singleton. | Task 5 |
| **Docker Compose** | ⬆ Improve | No MinIO. | Local S3 emulator needed. | Add `minio` to `docker-compose.yml`. | Task 6 |
