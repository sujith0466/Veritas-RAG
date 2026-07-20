#!/usr/bin/env bash
set -e
echo -e "\033[36mExecuting Alembic database migrations inside container...\033[0m"
docker compose exec backend alembic upgrade head
echo -e "\033[32m✅ Migrations applied successfully.\033[0m"
