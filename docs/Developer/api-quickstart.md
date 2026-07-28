# API Quick Start (5-Minute Guide)

This guide gets you executing your first query against the RAGuard AI API.

## Prerequisites
- RAGuard running locally (`docker-compose up -d`)
- A valid JWT token (or bypass auth in `development` environment)
- Tenant ID: `acme-corp`

## Step 1: Health Check
Verify the API is responsive:
```bash
curl http://localhost:8000/health
```

## Step 2: Ingest a Mock Document (Sandbox)
Before you can search, you need vectors in Qdrant. For testing without an ingestion pipeline, use the sandbox API to push a raw text string.
*(Note: Sandbox routes are only enabled in development)*
```bash
curl -X POST http://localhost:8000/api/v1/retrieval/sandbox/ingest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "tenant_id": "acme-corp",
    "text": "Enterprise refunds are available for 30 days after purchase."
  }'
```

## Step 3: Execute a Grounded Generation Query
Now, run a full end-to-end RAG query:
```bash
curl -X POST http://localhost:8000/api/v1/query/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "tenant_id": "acme-corp",
    "query": "What is the refund policy?",
    "top_k": 3
  }'
```

## Expected Response
```json
{
  "answer": "Enterprise refunds are available for 30 days after purchase.",
  "confidence_score": 0.98,
  "reliability_status": "HIGH",
  "citations": ["doc_sandbox_1"]
}
```

**Congratulations!** You have just executed a hybrid retrieval, confidence-scored, NLI-validated RAG query.
