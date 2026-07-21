# Disaster Recovery Runbook

## Scope
Total failure of the primary database (PostgreSQL) or vector store (Qdrant).

## Recovery Time Objective (RTO)
< 1 Hour

## Recovery Point Objective (RPO)
< 24 Hours

## Procedure: PostgreSQL Loss
1. Stop API traffic: `docker-compose stop api`
2. Locate latest backup in `/backups/postgres/`.
3. Execute restore script: `bash scripts/dr/restore_db.sh <latest_backup>`
4. Restart API: `docker-compose start api`
5. Verify application health via `/health`.

## Procedure: Qdrant Loss
1. Stop API traffic: `docker-compose stop api`
2. Restore latest Qdrant snapshot payload (via REST API).
3. If no snapshot exists, data must be re-ingested by triggering a full synchronization from the document source.
4. Restart API: `docker-compose start api`
