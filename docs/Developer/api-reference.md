# API Reference

All APIs are versioned under `/api/v1/`. Interactive documentation
is available at `http://localhost:8000/docs` (Swagger UI) when running locally.

## Authentication

All endpoints require a JWT Bearer token:
```
Authorization: Bearer <token>
```

## Endpoint Groups

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Overall health |
| GET | `/health/liveness` | Liveness probe |
| GET | `/health/readiness` | Readiness probe |

### Query & Retrieval
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/retrieval/search` | Hybrid semantic search |
| POST | `/api/v1/retrieval/sandbox` | Test retrieval without generation |
| GET | `/api/v1/retrieval/metrics` | Retrieval performance metrics |

### Generation & Validation
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/query/search` | End-to-end RAG query |
| GET | `/api/v1/validation/status` | Validation engine status |

### Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard/v1/executive/{tenant_id}` | Executive dashboard |
| GET | `/api/v1/dashboard/v1/governance/{tenant_id}` | SLA compliance |
| GET | `/api/v1/dashboard/v1/trends/{tenant_id}` | Hallucination trends |

### Alerts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/alerts/rules` | List alert rules |
| POST | `/api/v1/alerts/rules` | Create alert rule |
| POST | `/api/v1/alerts/fire` | Manually fire test alert |

### Reliability & Resilience
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/reliability/circuit-breaker` | Circuit breaker state |
| POST | `/api/v1/reliability/circuit-breaker/reset` | Force reset |
| GET | `/api/v1/resilience/v1/regions` | Region router status |
| POST | `/api/v1/resilience/v1/failover` | Trigger failover |

### Security & Compliance
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/Security/v1/audit/{tenant_id}` | Audit log |
| POST | `/api/v1/Security/v1/rotate` | Key rotation |

### Analytics & Quotas
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/analytics/quotas/{tenant_id}` | Quota status |
| GET | `/api/v1/analytics/roi/{tenant_id}` | ROI report |

### Intelligence
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/intelligence/v1/feedback` | Submit feedback |
| GET | `/api/v1/intelligence/v1/insights/{tenant_id}` | Optimization insights |

### Marketplace
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/marketplace/v1/bundles` | List bundles |
| POST | `/api/v1/marketplace/v1/install` | Install bundle |

### Observability
| Method | Path | Description |
|--------|------|-------------|
| GET | `/observability/v1/metrics` | Prometheus metrics |

## Error Format

```json
{
  "error_code": "AUTH_001",
  "message": "Authentication required",
  "http_status": 401,
  "correlation_id": "abc-123"
}
```
