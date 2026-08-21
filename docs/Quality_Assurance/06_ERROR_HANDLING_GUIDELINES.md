# Error Handling Guidelines

## Overview
Standardized error handling is critical for maintaining the reliability and debuggability of the Veritas RAG platform.

## Application Exception Strategy
The backend uses a standard `ApplicationException` that includes:
- `error_code`: A custom error code (e.g., `DOC_001`, `AUTH_003`, `RET_004`).
- `message`: A human-readable message.
- `status_code`: The HTTP status code to return.
- `details`: Optional dictionary containing further debugging information.

## Standard Error Codes

### Document Processing (`DOC_`)
- `DOC_001`: Document Not Found
- `DOC_002`: Unsupported File Type
- `DOC_003`: File Size Exceeds Limit
- `DOC_004`: Extraction Failed (e.g., OCR failed or PDF corrupted)
- `DOC_005`: Chunking Failed

### Retrieval and Vector Database (`RET_`)
- `RET_001`: Qdrant Connection Failed
- `RET_002`: Missing Collection
- `RET_003`: Embedding Generation Failed
- `RET_004`: Dense Search Failed
- `RET_005`: Reranking Failed

### Database and Infrastructure (`SYS_`)
- `SYS_001`: PostgreSQL Connection Failed
- `SYS_002`: Transaction Failed
- `SYS_003`: Redis Connection Failed (Celery Broker)

### Security and Validation (`VAL_`, `AUTH_`)
- `AUTH_001`: Missing Token
- `AUTH_002`: Invalid Token Signature
- `AUTH_003`: Token Expired
- `VAL_001`: Invalid Input Payload
- `VAL_004`: Path Traversal Detected

## Logging Guidelines
All exceptions should be logged using `structlog`. Include `correlation_id`, `tenant_id`, and `error_code` in all logs to facilitate distributed tracing.
