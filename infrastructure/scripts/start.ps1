#!/usr/bin/env pwsh
Write-Host "Starting RAGuard AI core stack..." -ForegroundColor Cyan
docker compose up -d
Write-Host "✅ Services running! UI: http://localhost:5173, API: http://localhost:8000" -ForegroundColor Green
