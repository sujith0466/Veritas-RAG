#!/usr/bin/env bash
set -e
echo -e "\033[33mCleaning dangling Docker images, build caches, and orphan containers...\033[0m"
docker system prune -f --volumes
docker builder prune -f
echo -e "\033[32m✅ System clean complete.\033[0m"
