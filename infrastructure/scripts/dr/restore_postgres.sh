#!/usr/bin/env bash
# ==============================================================================
# Disaster Recovery — PostgreSQL Database Restoration Script
#
# Usage:
#   ./restore_postgres.sh <path_to_backup.sql> [--confirm]
#
# Environment variables:
#   PGHOST (default: localhost)
#   PGPORT (default: 5432)
#   PGUSER (default: raguard)
#   PGDATABASE (default: raguard_db)
#   PGPASSWORD (optional)
#   ENVIRONMENT (default: development)
# ==============================================================================

set -euo pipefail

BACKUP_FILE="${1:-}"
CONFIRM_FLAG="${2:-}"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-raguard}"
PGDATABASE="${PGDATABASE:-raguard_db}"
ENVIRONMENT="${ENVIRONMENT:-development}"

# 1. Argument validation
if [[ -z "$BACKUP_FILE" ]]; then
    echo "[-] ERROR: Missing backup file argument." >&2
    echo "    Usage: $0 <path_to_backup.sql> [--confirm]" >&2
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "[-] ERROR: Backup file does not exist: $BACKUP_FILE" >&2
    exit 1
fi

if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "[-] ERROR: Backup file is empty: $BACKUP_FILE" >&2
    exit 1
fi

# 2. Production safety guard
if [[ "$ENVIRONMENT" == "production" ]] && [[ "$CONFIRM_FLAG" != "--confirm" ]]; then
    echo "[!] CAUTION: ENVIRONMENT is set to 'production'." >&2
    echo "    To execute destructive database restoration in production, pass '--confirm'." >&2
    exit 1
fi

echo "============================================================"
echo " Starting PostgreSQL Database Restoration"
echo " Target DB: $PGDATABASE on $PGHOST:$PGPORT"
echo " Backup:    $BACKUP_FILE"
echo " Env:       $ENVIRONMENT"
echo "============================================================"

# 3. Connectivity check
echo "[*] Checking PostgreSQL connectivity..."
if ! pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t 5 > /dev/null 2>&1; then
    echo "[-] ERROR: Cannot connect to PostgreSQL at $PGHOST:$PGPORT" >&2
    exit 2
fi

# 4. Terminate existing active connections to prevent lock conflicts
echo "[*] Terminating active connections to $PGDATABASE..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$PGDATABASE' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true

# 5. Restore database from dump
echo "[*] Restoring database schema and data..."
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -f "$BACKUP_FILE" > /dev/null 2>&1; then
    echo "[-] ERROR: psql restore command encountered errors." >&2
    exit 3
fi

# 6. Post-restoration verification
echo "[*] Verifying table counts after restoration..."
TABLE_COUNT=$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

TABLE_COUNT=$(echo "$TABLE_COUNT" | tr -d '[:space:]')

if [[ "$TABLE_COUNT" -eq 0 ]]; then
    echo "[-] ERROR: Table count in public schema is 0 after restoration!" >&2
    exit 4
fi

echo "[+] SUCCESS: PostgreSQL restore verified. Total tables restored: $TABLE_COUNT"
