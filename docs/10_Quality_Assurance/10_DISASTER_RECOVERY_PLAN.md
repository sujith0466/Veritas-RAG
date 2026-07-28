# Disaster Recovery Plan

## Infrastructure Components

### 1. PostgreSQL (Metadata)
- **Backup Strategy**: Daily automated snapshots via Supabase or AWS RDS.
- **Recovery**: Restore from the latest snapshot. RTO (Recovery Time Objective): 30 minutes. RPO (Recovery Point Objective): 24 hours.

### 2. Qdrant (Vector Database)
- **Backup Strategy**: Daily snapshot of Qdrant storage directory (`/qdrant/storage`).
- **Recovery**: Mount the snapshot directory to a new Qdrant container and restart. If vectors are lost but PostgreSQL is intact, a background Celery task can trigger a full re-embedding of all original documents (slower, but guarantees data reconstruction).

### 3. Redis (Message Broker & Cache)
- **Backup Strategy**: None. Redis is treated as ephemeral.
- **Recovery**: Restart the Redis container. In-flight Celery tasks will be lost and must be retried by the client or re-queued based on PostgreSQL document statuses (e.g., re-queuing any document stuck in `PROCESSING`).

### 4. Application State (Celery / API)
- Stateless architecture allows immediate scaling and recovery. Failed worker nodes can be replaced without data loss. Connection pools are isolated (using `NullPool` for Celery) to prevent cascading exhaustion failures.
