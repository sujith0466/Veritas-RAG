<#
.SYNOPSIS
    One-Command Turnkey Developer Onboarding & Bootstrap Script for RAGuard AI.
.DESCRIPTION
    Verifies prerequisites, initializes .env.local, validates configuration,
    builds multi-stage Docker images, boots services, checks health, and applies schema migrations.
#>

$ErrorActionPreference = "Stop"

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "         RAGuard AI — Turnkey Developer Bootstrap (Windows)             " -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

# 1. Prerequisite Check
Write-Host "`n[1/7] Auditing system prerequisites..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  ✅ Found Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Error: Docker Engine/Desktop is not running or not installed." -ForegroundColor Red
    exit 1
}

try {
    $composeVersion = docker compose version
    Write-Host "  ✅ Found Docker Compose: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Error: Docker Compose v2 is required." -ForegroundColor Red
    exit 1
}

# 2. Initialize .env.local
Write-Host "`n[2/7] Checking environment configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env.local")) {
    Write-Host "  ⚠️ .env.local not found. Securely initializing from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env.local" -Force
    Write-Host "  ✅ Created .env.local" -ForegroundColor Green
} else {
    Write-Host "  ✅ .env.local already present" -ForegroundColor Green
}

# 3. Pre-flight Environment Validation
Write-Host "`n[3/7] Running pre-flight environment validation..." -ForegroundColor Yellow
python infrastructure/env/validate_env.py --file .env.local
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Environment validation failed. Please fix .env.local errors above." -ForegroundColor Red
    exit 1
}

# 4. Multi-stage Docker Build
Write-Host "`n[4/7] Compiling multi-stage Docker images..." -ForegroundColor Yellow
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Docker build failed." -ForegroundColor Red
    exit 1
}

# 5. Launch Services
Write-Host "`n[5/7] Starting RAGuard AI services in background..." -ForegroundColor Yellow
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Service launch failed." -ForegroundColor Red
    exit 1
}

# 6. Polling Health SLAs
Write-Host "`n[6/7] Polling container health check endpoints (waiting for green)..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 1
$allHealthy = $false

while ($attempt -le $maxAttempts) {
    Start-Sleep -Seconds 2
    $unready = docker compose ps --format json | ConvertFrom-Json | Where-Object { $_.Health -ne "" -and $_.Health -ne "healthy" }

    if ($null -eq $unready -or $unready.Count -eq 0) {
        $allHealthy = $true
        break
    }
    Write-Host "  [$attempt/$maxAttempts] Waiting for health status..." -NoNewline
    $attempt++
}

if (-not $allHealthy) {
    Write-Host "`n  ⚠️ Some containers are still warming up. Checking health details via script..." -ForegroundColor Yellow
    ./infrastructure/scripts/health.ps1
} else {
    Write-Host "  ✅ All containers healthy and ready!" -ForegroundColor Green
}

# 7. Apply Alembic Migrations
Write-Host "`n[7/7] Executing database schema migrations against PostgreSQL..." -ForegroundColor Yellow
docker compose exec backend alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Database migrations encountered an issue. See logs above." -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================================================" -ForegroundColor Green
Write-Host "🎉 RAGuard AI local development environment is fully operational!" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "  🌐 Frontend React SPA   : http://localhost:5173" -ForegroundColor Cyan
Write-Host "  ⚡ FastAPI Backend API  : http://localhost:8000" -ForegroundColor Cyan
Write-Host "  📖 Swagger API Docs     : http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  ❤️ Liveness Health Check: http://localhost:8000/api/v1/health/live" -ForegroundColor Cyan
Write-Host "========================================================================`n" -ForegroundColor Green
