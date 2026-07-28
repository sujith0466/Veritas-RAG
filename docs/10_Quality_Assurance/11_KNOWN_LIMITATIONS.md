# Known Limitations (v1.0.1)

## 1. OCR Fallback Dependency
The ingestion pipeline gracefully falls back to OCR using Tesseract if standard PDF extraction fails (e.g., scanned documents). However, the default Celery worker container lacks `tesseract-ocr` installed at the OS level. Attempting to ingest purely scanned documents (or PDFs with < 50 extractable words) will trigger an `OCR_002` exception during processing.
**Workaround**: Ensure `tesseract-ocr` and `poppler-utils` are installed in the worker Docker image.

## 2. Multi-Tenant Collection Scaling
Currently, the system creates a unique Qdrant collection per tenant (`raguard_<tenant_id>`). While this ensures maximum security isolation, Qdrant may consume excessive memory if the tenant count scales beyond 1,000 active tenants per node due to HNSW index overhead.
**Workaround**: Future releases will migrate to a single shared collection using Qdrant's payload-level multi-tenancy partitioning.

## 3. Empty Tenant Search Behavior
Querying the search endpoint for a newly created tenant who has not uploaded any documents results in a `503 Service Unavailable` due to a Qdrant `404 Not Found` (Collection does not exist).
**Workaround**: The frontend should prevent searches until at least one document is successfully processed, or the backend should catch the 404 and return an empty result set safely.
