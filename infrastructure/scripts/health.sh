#!/usr/bin/env bash
set -e
echo -e "\033[36m========================================================================\033[0m"
echo -e "\033[36m                RAGuard AI — Three-Tier Health Probe Check              \033[0m"
echo -e "\033[36m========================================================================\033[0m"

echo -e "\n\033[33m[1/3] Checking Docker Compose Container Status...\033[0m"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n\033[33m[2/3] Probing API Tier 1 (Liveness) & Tier 2 (Readiness)...\033[0m"
if curl -s -f --max-time 3 http://localhost:8000/api/v1/health/live > /dev/null; then
    echo -e "  \033[32m✅ Liveness Probe  (/health/live) : OK\033[0m"
else
    echo -e "  \033[31m❌ Liveness Probe  (/health/live) : UNREACHABLE\033[0m"
fi

if curl -s -f --max-time 3 http://localhost:8000/api/v1/health/ready > /dev/null; then
    echo -e "  \033[32m✅ Readiness Probe (/health/ready): OK\033[0m"
else
    echo -e "  \033[31m❌ Readiness Probe (/health/ready): FAILED\033[0m"
fi

echo -e "\n\033[33m[3/3] Probing Frontend UI & Detailed Database Status...\033[0m"
if curl -s -f --max-time 3 http://localhost:5173 > /dev/null; then
    echo -e "  \033[32m✅ Frontend UI     (localhost:5173): OK (HTTP 200)\033[0m"
else
    echo -e "  \033[31m❌ Frontend UI     (localhost:5173): UNREACHABLE\033[0m"
fi

if curl -s -f --max-time 3 http://localhost:8000/api/v1/health/detailed > /dev/null; then
    echo -e "  \033[32m✅ Detailed Health (/health/detailed): OK\033[0m"
else
    echo -e "  \033[33m⚠️ Detailed Health (/health/detailed): Probing endpoint fallback or auth required.\033[0m"
fi
echo -e "\n\033[36m========================================================================\033[0m\n"
