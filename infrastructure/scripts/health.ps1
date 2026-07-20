#!/usr/bin/env pwsh
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "                RAGuard AI — Three-Tier Health Probe Check              " -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Checking Docker Compose Container Status..." -ForegroundColor Yellow
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`n[2/3] Probing API Tier 1 (Liveness) & Tier 2 (Readiness)..." -ForegroundColor Yellow
try {
    $live = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health/live" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "  ✅ Liveness Probe  (/health/live) : OK" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Liveness Probe  (/health/live) : UNREACHABLE ($($_.Exception.Message))" -ForegroundColor Red
}

try {
    $ready = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health/ready" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "  ✅ Readiness Probe (/health/ready): OK" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Readiness Probe (/health/ready): FAILED ($($_.Exception.Message))" -ForegroundColor Red
}

Write-Host "`n[3/3] Probing Frontend UI & Detailed Database Status..." -ForegroundColor Yellow
try {
    $ui = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($ui.StatusCode -eq 200) {
        Write-Host "  ✅ Frontend UI     (localhost:5173): OK (HTTP 200)" -ForegroundColor Green
    }
} catch {
    Write-Host "  ❌ Frontend UI     (localhost:5173): UNREACHABLE" -ForegroundColor Red
}

try {
    $detailed = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health/detailed" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "  ✅ Detailed Health (/health/detailed): status=$($detailed.status)" -ForegroundColor Green
    if ($null -ne $detailed.checks) {
        foreach ($key in $detailed.checks.PSObject.Properties.Name) {
            $check = $detailed.checks.$key
            Write-Host "     - ${key}: $($check.status) ($($check.latency_ms)ms)" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "  ⚠️ Detailed Health (/health/detailed): Probing endpoint fallback or auth required." -ForegroundColor Yellow
}
Write-Host "`n========================================================================`n" -ForegroundColor Cyan
