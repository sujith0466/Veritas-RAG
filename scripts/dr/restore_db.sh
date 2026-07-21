#!/usr/bin/env bash
# Postgres Restore Script
set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./restore_db.sh <backup_file.dump>"
    exit 1
fi

echo "Restoring database from $BACKUP_FILE..."
# Drop and recreate DB
docker-compose exec -T postgres dropdb -U raguard -f raguard_db || true
docker-compose exec -T postgres createdb -U raguard raguard_db

# Restore dump
cat $BACKUP_FILE | docker-compose exec -T postgres pg_restore -U raguard -d raguard_db
echo "Restore complete."
