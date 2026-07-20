#!/usr/bin/env bash
set -e
echo -e "\033[33mStopping RAGuard AI core stack...\033[0m"
docker compose down
echo -e "\033[32m🛑 Services stopped cleanly.\033[0m"
