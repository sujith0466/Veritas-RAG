#!/usr/bin/env bash
# Rolling deployment script for Docker Swarm / Compose
set -e

echo "Starting rolling deployment of RAGuard API..."

# Pull latest images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml pull

# Run database migrations
echo "Running database migrations..."
docker-compose -f docker-compose.yml run --rm api alembic upgrade head

# Deploy updates
# Docker Compose will use the `update_config: order: start-first` defined in docker-compose.prod.yml
echo "Applying updates..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps api

echo "Rolling deployment complete."
