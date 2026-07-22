# Known Limitations & Future Enhancements

While RAGuard AI v1.0.0 is certified production-ready for standard Enterprise RAG workloads, we believe in radical transparency regarding system capabilities. Below are the known minor limitations and planned enhancements for Version 2.

## 1. Retrieval & Chunking Limitations
- **PDF Extraction**: The current document ingestion pipeline utilizes a lightweight PDF parser optimized for standard text layouts. Complex documents containing dense tables, mathematical formulas, or multi-column newspaper layouts may suffer from suboptimal chunking. 
  - *Mitigation*: Users are advised to pre-process complex PDFs using OCR tools (e.g., Unstructured.io) before feeding them into RAGuard.
  - *Future Fix (v2)*: Native integration with advanced layout-aware parsing models (e.g., LlamaParse).
- **Reranking Constraint**: We currently utilize an in-memory cross-encoder for reranking. This provides excellent latency but scales poorly if the initial retrieval `k` is exceedingly large. Managed endpoints (e.g., Cohere Rerank) are not yet natively configurable via the UI.

## 2. Infrastructure & Scalability
- **Redis Dependency**: Circuit breakers and rate limiters rely exclusively on Redis. If Redis is unavailable, the system defaults to an "open" state (allowing traffic but disabling rate limits) rather than failing closed.
- **Horizontal Scaling**: While the API containers are stateless and can be horizontally scaled, the chunking and embedding workers currently run synchronously within the API request lifecycle (for immediate feedback). For massive batch uploads, this could lead to API timeouts.
  - *Future Fix (v2)*: Offload embedding tasks to a dedicated Celery/RabbitMQ worker queue.

## 3. Telemetry & Analytics
- **Custom Dashboards**: OpenTelemetry and Prometheus metrics are exposed, but custom Grafana dashboards are not bundled in the default `docker-compose.yml` to keep the footprint minimal. Operators must configure their own Grafana instances pointing to the RAGuard metrics endpoint.

## 4. LLM Provider Nuances
- **Streaming Responses**: The backend LLM Provider Manager supports Server-Sent Events (SSE) streaming, but the Frontend UI currently renders responses block-by-block. True character-by-character typing effects rely on polling the chunk cache.
- **Local Models**: Local model integration assumes an OpenAI-compatible endpoint (like Ollama or vLLM). Raw HuggingFace pipelines are not natively supported to maintain architectural simplicity.

## Summary
RAGuard AI v1.0 is highly stable within its intended operational envelope. The constraints above represent opportunities for scaling rather than fundamental flaws in the core reliability loop.
