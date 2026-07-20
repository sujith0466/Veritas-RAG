#!/usr/bin/env bash
set -e
echo -e "\033[36mStarting RAGuard AI core stack...\033[0m"
docker compose up -d
echo -e "\033[32m✅ Services running! UI: http://localhost:5173, API: http://localhost:8000\033[0m"
