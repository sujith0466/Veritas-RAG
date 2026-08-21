# Veritas RAG Qdrant Architecture

This document formalizes the vector database architecture using Qdrant for Veritas RAG Version 2.

## 1. Connection Lifecycle & Resilience

- **gRPC Preference:** All communication defaults to asynchronous gRPC to maximize throughput and enable multiplexing.
- **Client Caching:** The `AsyncQdrantClient` is securely cached per running event loop using weak references to prevent memory leaks during heavy concurrency.
- **Retry Policy:** Transient network failures (`httpx.ConnectError`, `ResponseHandlingException`) trigger a generic exponential backoff (`with_retry`). Non-transient validation errors (e.g., dimension mismatch, schema errors) fail fast and are never retried.

## 2. Multi-Tenant Namespace Strategy

Collections strictly enforce multi-tenant isolation via a centralized prefix mechanism.
- **Format:** `{collection_prefix}_{tenant_id}` (e.g., `raguard_tenant123`).
- **Enforcement:** The `CollectionNameBuilder` generates these namespaces centrally. Manual string concatenation for collection names is strictly prohibited.

## 3. Collection Lifecycle & Topology

Collections are provisioned dynamically before upsert sequences.

- **Vector Dimensions:** Dimensions are strictly dynamic. They are passed directly from the active embedding model's configuration via the `CollectionConfigDTO`. Hardcoding vector dimensions is prohibited to ensure multi-model support.
- **Distance Metric:** Supports Cosine, Dot, and Euclidean, configured per embedding model.
- **Quantization (ADR-M3-002):** INT8 Scalar Quantization is universally enabled for all collections. `always_ram=True` is applied to maintain sub-millisecond retrieval latency while cutting memory usage in half.
- **HNSW:** Collections natively utilize Qdrant's HNSW index structure.

## 4. Payload Schema and Filtering

To ensure fast hybrid search capabilities and strict metadata filtering (`ADR-M3-001`), the payload schema is highly controlled.

- **Canonical Payload Structure:**
  - `tenant_id`: UUID
  - `document_id`: UUID
  - `chunk_index`: Integer
  - `metadata`: JSON Object (key-value strings)
- **Index Strategy:** Payload indexes are automatically constructed (`PayloadSchemaType.KEYWORD`) for all heavily filtered fields (e.g., `document_id`, `tenant_id`).
- **Filtering Validation:** Operations like `search_points` and `delete_points_by_filter` accept an exact-match dictionary converted into `qdrant_models.Filter`.

## 5. Batch Operations

- **Configurable Limits:** The `QdrantSettings` injects `batch_size_limit` (default 100). Large documents must be chunked and streamed in accordance with this limit to prevent gRPC frame size violations and memory spikes.

## 6. Observability

- **Metrics Foundation (`QdrantMetrics`):**
  - Tracks absolute volume for searches, upserts, collection creations, and index creations.
  - Aggregates rolling average latencies for both `search` and `upsert` operations.
  - Monitors connection resilience by counting `retries` and `errors`.
- **Health Checks:** The standard `/health` probe actively pings `get_collections()` and returns detailed telemetry including latency in milliseconds, total available collections, and the active gRPC transport status.

## 7. Architectural Agnosticism

The `BaseVectorDBProvider` exposes high-level Python domain objects (`VectorPointDTO`, `CollectionConfigDTO`). The `QdrantProvider` encapsulates all Qdrant-specific SDK logic, ensuring that Veritas RAG could theoretically swap to another provider (e.g., Milvus, Pinecone) without modifying any upstream business logic.
