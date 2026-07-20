#!/usr/bin/env bash
set -e
echo -e "\033[31m========================================================================\033[0m"
echo -e "\033[31m  ⚠️  WARNING: Resetting all RAGuard containers and persistent volumes!\033[0m"
echo -e "\033[31m========================================================================\033[0m"

read -p "Type 'YES' to confirm full environment teardown and data wipe: " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    echo -e "\033[33mReset cancelled.\033[0m"
    exit 0
fi

echo -e "\033[33mTearing down containers, networks, and named volumes...\033[0m"
docker compose down -v --remove-orphans
echo -e "\033[32m✅ Reset complete. Run make setup or ./infrastructure/scripts/bootstrap.sh to re-initialize.\033[0m"
