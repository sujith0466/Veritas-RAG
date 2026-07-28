# Architecture Walkthrough

This document guides developers through the control flow of a request in RAGuard AI.

## 1. Gateway & Middleware
All requests enter `backend/api/v1/`. Middlewares automatically extract JWT claims, enforce RBAC, and assign an OpenTelemetry Trace ID.

## 2. Query Intelligence (`backend/modules/query_intelligence`)
The query is passed to the `IntentExtractor`. If `DLP_ENABLED=true`, PII is redacted here.

## 3. Hybrid Retrieval (`backend/modules/retrieval`)
The service executes concurrent calls to Qdrant (Dense) and PostgreSQL/BM25 (Sparse). Results are merged using Reciprocal Rank Fusion (RRF).

## 4. Confidence Engine (`backend/modules/confidence`)
The `CoverageAnalyzer` determines if the retrieved chunks sufficiently cover the semantic meaning of the user query. The `ConflictDetector` checks if chunks contradict each other.

## 5. Retry Controller (`backend/modules/retry`)
If confidence is `< 0.6` and `RETRY_ENABLED=true`, the engine automatically rewrites the query or pauses to ask the user for clarification.

## 6. Generation (`backend/modules/generation`)
The prompt is constructed by strictly binding the retrieved context. The LLM is called via `BaseLLMProvider`.

## 7. Validation (`backend/modules/validation`)
The LLM response is checked against the source chunks using Natural Language Inference (NLI). Any ungrounded hallucination flags the response.

## 8. Return
The final JSON payload, along with observability metrics and audit logs, is dispatched to the client.
