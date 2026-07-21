#!/usr/bin/env bash
# RAGuard AI - Graceful Shutdown Script
echo "Stopping RAGuard AI..."
docker-compose down --timeout 30
echo "RAGuard AI stopped."
