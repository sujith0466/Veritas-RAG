#!/usr/bin/env pwsh
Write-Host "========================================================================" -ForegroundColor Red
Write-Host "  ⚠️  WARNING: Resetting all RAGuard containers and persistent volumes!" -ForegroundColor Red
Write-Host "========================================================================" -ForegroundColor Red

$confirmation = Read-Host "Type 'YES' to confirm full environment teardown and data wipe"
if ($confirmation -ne "YES") {
    Write-Host "Reset cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host "Tearing down containers, networks, and named volumes..." -ForegroundColor Yellow
docker compose down -v --remove-orphans
Write-Host "✅ Reset complete. Run ./infrastructure/scripts/bootstrap.ps1 to re-initialize." -ForegroundColor Green
