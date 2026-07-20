#!/usr/bin/env pwsh
Write-Host "Executing Alembic database migrations inside container..." -ForegroundColor Cyan
docker compose exec backend alembic upgrade head
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Migrations applied successfully." -ForegroundColor Green
} else {
    Write-Host "❌ Migration check encountered an error." -ForegroundColor Red
    exit 1
}
