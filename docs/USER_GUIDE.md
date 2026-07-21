# User Guide

## What is RAGuard?

RAGuard AI is an enterprise reliability layer that sits between your
application and its AI model, ensuring every AI response is:
- **Grounded** in actual retrieved documents
- **Validated** via natural language inference
- **Cited** with traceable source references
- **Scored** with a confidence level

## Submitting a Query

```http
POST /api/v1/query/search
Content-Type: application/json
Authorization: Bearer <token>

{
  "query": "What is the refund policy for enterprise licenses?",
  "tenant_id": "acme-corp",
  "top_k": 5
}
```

## Understanding the Response

```json
{
  "answer": "Enterprise license refunds are available within 30 days...",
  "confidence_score": 0.91,
  "sources": ["doc_123", "doc_456"],
  "reliability_status": "HIGH",
  "citations": ["Section 4.2 of Enterprise License Agreement"]
}
```

| Field | Description |
|-------|-------------|
| `confidence_score` | 0.0-1.0 composite reliability score |
| `reliability_status` | `HIGH`, `MEDIUM`, `LOW`, `UNRESOLVABLE` |
| `citations` | Verifiable source references |

## Feedback Submission

Help RAGuard improve by submitting feedback:

```http
POST /api/v1/intelligence/v1/feedback
{
  "query_id": "q-abc-123",
  "feedback_type": "THUMBS_UP"
}
```
