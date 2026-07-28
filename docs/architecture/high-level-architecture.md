# RAGuard AI — High-Level Architecture

## Component Diagram

```
+------------------+     HTTPS      +------------------------+
|   Client / UI    | ------------> |     API Gateway         |
+------------------+               |  (FastAPI + Middleware) |
                                   +------------------------+
                                              |
                    +-------------------------+-------------------------+
                    |                         |                         |
          +---------v----------+   +----------v----------+   +---------v----------+
          |  Query Intelligence |   |  Hybrid Retrieval   |   |  Confidence Engine |
          +---------+----------+   +----------+----------+   +---------+----------+
                    |                         |                         |
          +---------v----------+   +----------v----------+   +---------v----------+
          |  Retry Controller  |   |    Generation Layer  |   |  Reflection Engine |
          +---------+----------+   +----------+----------+   +---------+----------+
                    |                         |                         |
                    +-------------------------+-------------------------+
                                              |
                                   +----------v----------+
                                   |   Validation Layer  |
                                   +----------+----------+
                                              |
                    +-------------------------+-------------------------+
                    |                         |                         |
          +---------v----------+   +----------v----------+   +---------v----------+
          |    Observability   |   |     Analytics       |   |    Security/DLP    |
          +--------------------+   +---------------------+   +--------------------+
```

## Infrastructure

| System | Technology | Purpose |
|--------|-----------|---------|
| Application | FastAPI (Python 3.13) | REST API server |
| Vector DB | Qdrant | Dense embedding search |
| Relational DB | PostgreSQL 15 | Structured data |
| Cache | Redis 7 | State, quotas, dedup |
| Background | Celery (optional) | Async task processing |
| Monitoring | Prometheus + Grafana | Metrics |
| Tracing | OpenTelemetry | Distributed traces |
