#!/usr/bin/env bash
# ==============================================================================
# RAGuard AI — Turnkey Developer Bootstrap Script (Linux / macOS / Git Bash)
# ==============================================================================

set -e

echo -e "\033[36m========================================================================\033[0m"
echo -e "\033[36m          RAGuard AI — Turnkey Developer Bootstrap (POSIX)              \033[0m"
echo -e "\033[36m========================================================================\033[0m"

# 1. Prerequisite Check
echo -e "\n\033[33m[1/7] Auditing system prerequisites...\033[0m"
if ! command -v docker &> /dev/null; then
    echo -e "  \033[31m❌ Error: Docker is not installed or not in PATH.\033[0m"
    exit 1
fi
echo -e "  \033[32m✅ Found Docker: $(docker --version)\033[0m"

if ! docker compose version &> /dev/null; then
    echo -e "  \033[31m❌ Error: Docker Compose v2 is required.\033[0m"
    exit 1
fi
echo -e "  \033[32m✅ Found Docker Compose: $(docker compose version)\033[0m"

# 2. Initialize .env.local
echo -e "\n\033[33m[2/7] Checking environment configuration...\033[0m"
if [ ! -f ".env.local" ]; then
    echo -e "  \033[33m⚠️ .env.local not found. Securely initializing from .env.example...\033[0m"
    cp .env.example .env.local
    echo -e "  \033[32m✅ Created .env.local\033[0m"
else
    echo -e "  \033[32m✅ .env.local already present\033[0m"
fi

# 3. Pre-flight Environment Validation
echo -e "\n\033[33m[3/7] Running pre-flight environment validation...\033[0m"
python3 infrastructure/env/validate_env.py --file .env.local || python infrastructure/env/validate_env.py --file .env.local

# 4. Multi-stage Docker Build
echo -e "\n\033[33m[4/7] Compiling multi-stage Docker images...\033[0m"
docker compose build

# 5. Launch Services
echo -e "\n\033[33m[5/7] Starting RAGuard AI services in background...\033[0m"
docker compose up -d

# 6. Polling Health SLAs
echo -e "\n\033[33m[6/7] Polling container health check endpoints (waiting for green)...\033[0m"
MAX_ATTEMPTS=30
ATTEMPT=1
ALL_HEALTHY=false

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    sleep 2
    UNREADY=$(docker compose ps --format json | grep -c '"Health":"unhealthy"' || true)
    WAITING=$(docker compose ps --format json | grep -c '"Health":"starting"' || true)
    
    if [ "$UNREADY" -eq 0 ] && [ "$WAITING" -eq 0 ]; then
        ALL_HEALTHY=true
        break
    fi
    echo -n "  [$ATTEMPT/$MAX_ATTEMPTS] Waiting for health status... "
    ATTEMPT=$((ATTEMPT+1))
done

if [ "$ALL_HEALTHY" = false ]; then
    echo -e "\n  \033[33m⚠️ Some containers are still warming up. Inspecting status...\033[0m"
    ./infrastructure/scripts/health.sh || true
else
    echo -e "  \033[32m✅ All containers healthy and ready!\033[0m"
fi

# 7. Apply Alembic Migrations
echo -e "\n\033[33m[7/7] Executing database schema migrations against PostgreSQL...\033[0m"
docker compose exec backend alembic upgrade head

echo -e "\n\033[32m========================================================================\033[0m"
echo -e "\033[32m🎉 RAGuard AI local development environment is fully operational!\033[0m"
echo -e "\033[32m========================================================================\033[0m"
echo -e "  \033[36m🌐 Frontend React SPA   : http://localhost:5173\033[0m"
echo -e "  \033[36m⚡ FastAPI Backend API  : http://localhost:8000\033[0m"
echo -e "  \033[36m📖 Swagger API Docs     : http://localhost:8000/docs\033[0m"
echo -e "  \033[36m❤️ Liveness Health Check: http://localhost:8000/api/v1/health/live\033[0m"
echo -e "\033[32m========================================================================\033[0m\n"
