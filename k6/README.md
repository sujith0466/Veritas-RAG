# Veritas RAG V2 — k6 Load & Concurrency Testing Suite (F15.2)

**Epic:** Epic 15 — Production Hardening & Enterprise Security
**Feature:** F15.2 — Load Testing (Concurrent Users, Bulk Ingestion & Atomic Quota Accumulation)
**Status:** FRAMEWORK IMPLEMENTED / READY FOR STAGING EXECUTION

---

## 1. Overview

This directory contains the production-grade **k6 Open Source** performance, concurrency, and stress test suites for the Veritas RAG V2 Multi-Tenant AI Platform.

---

## 2. Test Scenarios Directory

| Scenario Script | Primary Target | VU Target | Core Verification |
|:---|:---|:---:|:---|
| [`scenarios/auth_workload.js`](file:///d:/Veritas RAG/k6/scenarios/auth_workload.js) | `/api/v1/auth/login` | 100 VUs | Session generation rate & token auth latency |
| [`scenarios/concurrent_users.js`](file:///d:/Veritas RAG/k6/scenarios/concurrent_users.js) | `/api/v1/workspaces/*` | 100 VUs | Multi-tenant workspace browsing under load |
| [`scenarios/chat_streaming.js`](file:///d:/Veritas RAG/k6/scenarios/chat_streaming.js) | `/api/v1/chat/stream` | 50 Streams | SSE streaming stability & first-token latency |
| [`scenarios/document_upload.js`](file:///d:/Veritas RAG/k6/scenarios/document_upload.js) | `/api/v1/documents/upload` | 50 VUs | Ingestion throughput & payload processing |
| [`scenarios/quota_concurrent_increment.js`](file:///d:/Veritas RAG/k6/scenarios/quota_concurrent_increment.js) | `/analytics/v1/workspace-usage/*` | 50 VUs / 100 Req | **Mandatory atomic UPSERT counter race-condition test** |
| [`scenarios/mixed_enterprise_workload.js`](file:///d:/Veritas RAG/k6/scenarios/mixed_enterprise_workload.js) | Blended Endpoints | 85 VUs | Realistic multi-user enterprise workload |

---

## 3. Mandatory Atomic Quota Scenario

The test [`scenarios/quota_concurrent_increment.js`](file:///d:/Veritas RAG/k6/scenarios/quota_concurrent_increment.js) explicitly evaluates the atomic accumulation guarantee introduced in Feature F13.2:
- Generates 100 concurrent requests against a single shared workspace ID.
- Computes `expected_tokens = initial_tokens + (tokens_per_req * successful_reqs)`.
- Compares the initial state against the final persisted state in PostgreSQL.
- Fails if race conditions or lost updates occur.

---

## 4. Execution Guide

### Prerequisites
- Install k6: `choco install k6` (Windows) or `brew install k6` (macOS) or `apt-get install k6` (Linux).
- Deploy staging environment: `docker-compose up -d`.

### Running All Scenarios
```bash
bash k6/run_all.sh http://localhost:8000
```

### Running Individual Scenarios
```bash
# Atomic quota test
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/quota_concurrent_increment.js

# Chat streaming test
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/chat_streaming.js
```
