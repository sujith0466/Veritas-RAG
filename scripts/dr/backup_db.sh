#!/usr/bin/env bash
# Automated Postgres Backup Script
set -e

BACKUP_DIR="/backups/postgres"
mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +%F_%T)

echo "Starting PostgreSQL backup: $TIMESTAMP"
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U raguard -F c raguard_db > $BACKUP_DIR/raguard_$TIMESTAMP.dump

# Keep last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -name "*.dump" -delete
echo "Backup complete."
