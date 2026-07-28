# Debugging Guide

## 1. Reading Logs
Logs are structured as JSON. To read them effectively locally:
```bash
docker-compose logs -f api | jq '.'
```

## 2. Tracing a Request
1. Extract the `trace_id` from the HTTP response headers (`X-Trace-Id`).
2. Search your logging aggregator (or stdout) for that `trace_id`.
3. The logs will reveal the exact Latency, Confidence Score, and LLM Provider used for that specific request.

## 3. Disabling Safety Fences (Local Only)
If you need to test raw components without circuit breakers triggering:
Edit `.env`:
```env
RETRY_ENABLED=false
REFLECTION_ENABLED=false
```
Restart the API: `docker-compose restart api`
