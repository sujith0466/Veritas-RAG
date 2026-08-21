# Veritas RAG Storage Architecture

This document formalizes the object storage architecture for Veritas RAG Version 2.

## 1. Provider Agnosticism and Factory Injection

- **Single Abstraction:** All object interactions exclusively use `backend.document.storage.base.StorageProvider`.
- **Factory Pattern:** The `StorageProviderFactory` conditionally instantiates either `LocalStorageProvider` or `S3StorageProvider`.
- **Duplicate Prevention:** Component-specific implementations (e.g., dedicated avatar storage providers) are strictly forbidden to ensure architectural consistency.

## 2. Multi-Tenant Namespace Strategy

- **Bucket Definitions:** The `BucketNameBuilder` controls raw bucket resolution (`raguard-documents`, `raguard-audit-logs`).
- **Versioned Paths:** The `get_versioned_path()` function enforces physical tenant isolation:
  `documents/{tenant_id}/{document_id}/v{version_number}/{category}/{filename}`
  This layout natively supports granular multi-tenant deletion and version rollback without cross-contamination.

## 3. Resilience and Retry Policies

- **Selective Retries:** Operations against cloud storage are wrapped in `with_retry`.
- **Transient Constraints:** The retry mechanism is strictly limited to transient connection/transport errors (e.g., `EndpointConnectionError`, HTTP 5xx).
- **Fail Fast:** Deterministic errors like `AccessDenied`, `NoSuchBucket`, `NoSuchKey`, and checksum mismatches fail immediately, generating actionable `DocumentDomainException` codes (`STORE_001`, `STORE_002`).

## 4. Initialization, Versioning, and WORM

- **Idempotent Initialization:** The `initialize_buckets()` startup routine automatically creates buckets safely (ignoring `BucketAlreadyExists`).
- **Versioning:** Bucket versioning is enabled by default to protect against accidental overwrites prior to processing completion.
- **Object Lock (WORM):** The `audit_logs` bucket is initialized with S3 Object Lock (Governance Mode, 7 years) to guarantee tamper-proof audit trails for compliance. This logic is fully isolated to the initialization scripts.

## 5. Security and Data Access

- **Presigned URLs:** Physical asset serving is abstracted via `create_download_url()` and `create_upload_url()`. Veritas RAG acts exclusively as an orchestrator; large binary transfers occur directly between the client and the S3 bucket using these secure, time-bound URLs.
- **Path Traversal Mitigation:** The `LocalStorageProvider` aggressively resolves and validates directory structures to prevent malicious relative path escapes.

## 6. Observability

The `StorageMetrics` singleton instrumentally tracks:
- Upload / Download throughput (`bytes_uploaded`, `bytes_downloaded`)
- Activity rates (`upload_count`, `download_count`, `delete_count`)
- Precision latencies (`upload_latency_ms`, `download_latency_ms`)
- Resilience overhead (`retries`, `failures`)

## 7. The Processing Contract (`CONTRACT_001`)

The `DocumentProcessingContract` serves as the final arbiter before a document transitions to a processed state. It rigorously asserts the existence of the `original` binary, the `normalized` text artifact, and the canonical `manifest.json`. Without these artifacts successfully verified via the `StorageProvider`, the ingestion pipeline will permanently halt.
