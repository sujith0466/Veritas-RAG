#!/usr/bin/env bash
set -e
echo -e "\033[36mStreaming multi-service logs (Press Ctrl+C to exit)...\033[0m"
docker compose logs -f --tail=100
