#!/usr/bin/env pwsh
Write-Host "Restarting RAGuard AI services..." -ForegroundColor Cyan
docker compose restart
Write-Host "🔄 Services restarted." -ForegroundColor Green
