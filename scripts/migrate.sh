#!/usr/bin/env bash
# Run Alembic migrations
set -e
echo "Running Alembic migrations..."
alembic upgrade head
echo "Migrations complete."
