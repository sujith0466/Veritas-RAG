#!/usr/bin/env pwsh
Write-Host "Streaming multi-service logs (Press Ctrl+C to exit)..." -ForegroundColor Cyan
docker compose logs -f --tail=100
