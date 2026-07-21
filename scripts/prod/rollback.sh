#!/usr/bin/env bash
# Rollback script
set -e

TARGET_VERSION=$1

if [ -z "$TARGET_VERSION" ]; then
    echo "Usage: ./rollback.sh <version_tag>"
    exit 1
fi

echo "Rolling back to RAGuard API version $TARGET_VERSION..."

# Re-tag and deploy previous version
export API_IMAGE_TAG=$TARGET_VERSION
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps api

echo "Rollback initiated. Monitor /health/readiness for status."
