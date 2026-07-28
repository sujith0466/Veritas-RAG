# Vector Database Schema

## Qdrant Configuration

RAGuard AI provisions Qdrant collections dynamically per tenant upon their first document ingestion.

### Collection Settings
- **Name**: `raguard_<tenant_id>`
- **Vector Size**: 384 (Matched to `bge-small-en-v1.5`)
- **Distance Metric**: Cosine Distance
- **On-Disk Storage**: Enabled for HNSW index and vector payloads to optimize memory usage.

### Payload Schema
Every point in Qdrant corresponds to a document chunk. The payload includes:
- `document_id` (UUID string)
- `version_id` (UUID string)
- `tenant_id` (UUID string)
- `chunk_index` (Integer)
- `text` (String - the actual chunk content)
- `page_number` (Integer, optional)

### Indexing Strategy
- Payload indices are created on `document_id` and `tenant_id` to speed up exact-match filtering.
