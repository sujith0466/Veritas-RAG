<div align="center">
  <h1>⚠️ Known Limitations & Future Enhancements</h1>
  <p><b>Radical transparency regarding RAGuard's operational envelope.</b></p>
</div>

---

While RAGuard AI v1.0.0 is certified production-ready for standard Enterprise RAG workloads, we believe in being completely transparent about system constraints and boundaries. Below are the known minor limitations and our engineering team's planned mitigation strategies for future versions.

## 📄 1. Retrieval & Document Ingestion
- **Complex PDF Layouts:** The current document ingestion pipeline utilizes a lightweight PDF parser optimized for standard corporate text layouts (memos, reports, contracts). Complex documents containing dense nested tables, mathematical formulas, or multi-column newspaper layouts may experience suboptimal chunking boundaries.
  - *Current Workaround:* Users are advised to pre-process complex PDFs using specialized OCR/Layout engines (e.g., Unstructured.io) before feeding them into the RAGuard API.
  - *Future Fix (v1.2):* Native integration with advanced vision-based layout parsers (e.g., LlamaParse).
- **Reranking Bottlenecks:** We currently utilize a high-performance in-memory cross-encoder for reranking. This provides excellent latency but scales poorly if the initial retrieval `k` is exceedingly large (e.g., > 100 documents).
  - *Future Fix (v1.1):* UI and API support for dynamically delegating to managed reranking endpoints (e.g., Cohere Rerank API).

## 🏗️ 2. Infrastructure & Scalability
- **Redis Coupling:** Our global circuit breakers and request rate limiters rely exclusively on Redis. If the Redis cluster becomes unavailable, the system correctly fails "open" (allowing traffic to proceed without strict rate limits) rather than failing closed (blocking all traffic), but this temporarily degrades DoS protections.
- **Synchronous Chunking:** While the stateless API containers scale horizontally with ease, document chunking and embedding operations currently block synchronously within the API request lifecycle to provide immediate UI feedback. For massive batch uploads (gigabytes of text), this will trigger HTTP timeouts.
  - *Future Fix (v1.2):* Offload heavy embedding tasks to a dedicated asynchronous worker queue (Celery/RabbitMQ) with websocket progress updates to the UI.

## 📊 3. Telemetry & Analytics
- **Dashboard Bundling:** OpenTelemetry and Prometheus metrics are heavily instrumented throughout the backend, but pre-built Grafana dashboard configurations are not bundled in the default Docker Compose configuration to keep the initial footprint minimal.
  - *Current Workaround:* DevOps operators must attach their own Grafana or Datadog instances pointing to the `/metrics` endpoint.

## 🤖 4. LLM Provider Nuances
- **UI Streaming Latency:** The backend LLM Provider Manager natively supports Server-Sent Events (SSE) streaming, but the Frontend UI currently renders validation responses block-by-block. True character-by-character typing effects rely on polling the chunk cache.
- **Local Model Constraints:** Local LLM integration assumes an OpenAI-compatible interface (such as Ollama or vLLM). Raw HuggingFace pipeline deployment is not natively supported to maintain architectural simplicity across the routing layer.

---

### Summary
RAGuard AI v1.0 is highly stable within its intended operational bounds. The constraints outlined above represent structural scaling opportunities for hyper-growth environments, rather than fundamental flaws in the core reliability loops.
