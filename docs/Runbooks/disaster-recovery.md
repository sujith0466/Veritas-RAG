# Disaster Recovery Runbook

## Scope
Total failure of the primary database (PostgreSQL) or vector store (Qdrant).

## Recovery Time Objective (RTO)
< 1 Hour (Target: ≤ 4 Hours in cross-region scenarios)

## Recovery Point Objective (RPO)
< 24 Hours (Target: ≤ 6 Hours)

## Procedure: PostgreSQL Loss
1. Stop API traffic: `docker-compose stop backend` or `kubectl scale deployment/raguard-api --replicas=0`
2. Locate latest backup in `/backup/` (from `postgres-backup-pvc`).
3. Execute restore script: `bash infrastructure/scripts/dr/restore_postgres.sh <latest_backup.sql>`
4. Restart API: `docker-compose start backend` or `kubectl scale deployment/raguard-api --replicas=3`
5. Verify application health: `bash infrastructure/scripts/dr/verify_restore.sh`

## Procedure: Qdrant Loss
1. Stop API traffic: `docker-compose stop backend` or `kubectl scale deployment/raguard-api --replicas=0`
2. Restore latest Qdrant snapshot: `bash infrastructure/scripts/dr/restore_qdrant.sh knowledge <snapshot_name_or_url>`
3. If no snapshot exists, trigger background full vector re-indexing from PostgreSQL document metadata.
4. Restart API: `docker-compose start backend` or `kubectl scale deployment/raguard-api --replicas=3`
5. Verify application health: `bash infrastructure/scripts/dr/verify_restore.sh`
