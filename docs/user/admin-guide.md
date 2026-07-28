# Admin Guide

## Tenant Management

Create a new tenant:
```http
POST /api/v1/tenants
{
  "tenant_id": "new-corp",
  "display_name": "New Corporation",
  "quota_tokens_per_month": 1000000
}
```

## Quota Management

View current usage:
```http
GET /api/v1/analytics/quotas/new-corp
```

Update quota:
```http
PUT /api/v1/analytics/quotas/new-corp
{"limit_tokens_per_month": 2000000}
```

## Alert Rules

Configure a reliability alert:
```http
POST /api/v1/alerts/rules
{
  "rule_name": "LowConfidenceSpike",
  "condition": "avg_confidence < 0.5",
  "window_minutes": 5,
  "channels": ["slack", "pagerduty"]
}
```

## Key Rotation

Rotate a provider API key:
```http
POST /api/v1/security/v1/rotate
{
  "tenant_id": "new-corp",
  "provider": "openai",
  "new_key": "sk-..."
}
```

## Audit Logs

```http
GET /api/v1/security/v1/audit/new-corp
```
