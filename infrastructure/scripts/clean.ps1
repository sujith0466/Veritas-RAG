#!/usr/bin/env pwsh
Write-Host "Cleaning dangling Docker images, build caches, and orphan containers..." -ForegroundColor Yellow
docker system prune -f --volumes
docker builder prune -f
Write-Host "✅ System clean complete." -ForegroundColor Green
