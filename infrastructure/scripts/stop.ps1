#!/usr/bin/env pwsh
Write-Host "Stopping RAGuard AI core stack..." -ForegroundColor Yellow
docker compose down
Write-Host "🛑 Services stopped cleanly." -ForegroundColor Green
