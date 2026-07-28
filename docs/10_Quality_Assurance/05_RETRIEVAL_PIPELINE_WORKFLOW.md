# Retrieval Pipeline Workflow

## Overview
This document outlines the complete Retrieval-Augmented Generation (RAG) pipeline workflow utilized by the RAGuard AI platform.

## 1. Query Processing
- **Input**: User submits a query via the `/api/v1/retrieval/search` endpoint.
- **Validation**: Payload is validated against Pydantic models. Tenant ID is extracted from the JWT token.
- **Routing**: The query is routed to the `RetrievalService`.

## 2. Dense Vector Search (Qdrant)
- The user's query is embedded using the configured embedding model (`bge-small-en-v1.5` or equivalent).
- A dense vector search is executed against the tenant-specific Qdrant collection (`raguard_<tenant_id>`).
- Filter payloads enforce tenant-level isolation if multiple tenants share a broader collection (though current architecture uses one collection per tenant).
- Top-K results (default `top_k=5`) are returned.

## 3. Sparse / Keyword Search (Elasticsearch/BM25)
- (Reserved for Hybrid Search architecture)
- BM25 score calculation.

## 4. Reranking (Cross-Encoder)
- The combined results from Dense/Sparse searches are passed to a Cross-Encoder Reranker.
- Results are rescored based on actual semantic relevance to the query.
- The highest-scoring `top_k` chunks are retained.

## 5. Generation (LLM)
- The top chunks are injected into the system prompt context window.
- The language model generates the final grounded response.
- Citations (document names, chunk indices) are mapped back to the original payload.

## 6. Response
- The generated text and citations are returned to the client in the standard API response format.
