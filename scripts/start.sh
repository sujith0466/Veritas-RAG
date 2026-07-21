#!/usr/bin/env bash
# RAGuard AI - Production Startup Script
set -e

echo "Starting RAGuard AI v1.0.0..."

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting API server..."
exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-4}" \
    --log-level "${LOG_LEVEL:-info}"
