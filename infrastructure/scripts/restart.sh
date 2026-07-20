#!/usr/bin/env bash
set -e
echo -e "\033[36mRestarting RAGuard AI services...\033[0m"
docker compose restart
echo -e "\033[32m🔄 Services restarted.\033[0m"
