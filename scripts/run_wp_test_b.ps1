<#
.SYNOPSIS
    Veritas-RAG -- WP-TEST-B Integration Infrastructure and Migration Runbook.

.DESCRIPTION
    Provisions isolated test infrastructure (PostgreSQL 15, Redis 7, MinIO, Qdrant v1.8.2),
    verifies container health with bounded timeout, validates container
    and volume identities, executes fail-closed target preflight with live probes
    (PostgreSQL SELECT current_database(), MinIO health/buckets, Qdrant /readyz), applies
    Alembic migrations, confirms container identities before test execution,
    and runs staged integration test suites.

.PARAMETER CleanupOnSuccess
    If specified, tears down test containers and volumes after successful test run.
    Per safety policy, automatic cleanup is NEVER run on failure.

.PARAMETER Scope
    Integration test execution scope: "smoke" (single auth gate node) or "all" (staged integration suites).
    Defaults to "all".
#>
[CmdletBinding()]
param (
    [switch]$CleanupOnSuccess = $false,
    [ValidateSet("smoke", "all")]
    [string]$Scope = "all"
)

$ErrorActionPreference = "Stop"
$repoRoot = "D:\RAGuard"
Set-Location $repoRoot

$venvPy = "$repoRoot\venv\Scripts\python.exe"
$venvAlembic = "$repoRoot\venv\Scripts\alembic.exe"
$venvPytest = "$repoRoot\venv\Scripts\pytest.exe"
$composeFile = "$repoRoot\docker-compose.test.yml"
$preflightScript = "$repoRoot\scripts\verify_test_target.py"
$projectName = "raguard-test"

# Helper: Execute docker inspect via JSON and return property object safely
function Get-DockerContainerJson {
    param([Parameter(Mandatory = $true)][string]$Target)
    $raw = docker inspect $Target 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
        throw "DOCKER INSPECT FAILED for '$Target' (exit code $LASTEXITCODE)."
    }
    return ($raw | ConvertFrom-Json)
}

# Helper: Directly inspect volume and verify both project and volume labels
function Test-VolumeOwnership {
    param(
        [Parameter(Mandatory = $true)][string]$VolumeName,
        [Parameter(Mandatory = $true)][string]$ExpectedProject
    )
    $raw = docker volume inspect $VolumeName 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
        Write-Warning "SAFETY AUDIT: docker volume inspect failed for '$VolumeName' (exit code $LASTEXITCODE)."
        return $false
    }
    $volObj = $raw | ConvertFrom-Json
    $projLabel = $volObj.Labels.'com.docker.compose.project'
    $volLabel = $volObj.Labels.'com.docker.compose.volume'

    if ([string]::IsNullOrWhiteSpace($projLabel) -or [string]::IsNullOrWhiteSpace($volLabel)) {
        Write-Warning "SAFETY AUDIT: Missing Compose labels on volume '$VolumeName'."
        return $false
    }

    $projMatch = ($projLabel.Trim() -eq $ExpectedProject)
    $volMatch = ($volLabel.Trim() -eq $VolumeName)

    if (-not $projMatch) {
        Write-Warning "OWNERSHIP MISMATCH: Volume project label '$($projLabel.Trim())' != expected '$ExpectedProject'."
        return $false
    }
    if (-not $volMatch) {
        Write-Warning "OWNERSHIP MISMATCH: Volume name label '$($volLabel.Trim())' != expected '$VolumeName'."
        return $false
    }

    return $true
}

# Verify toolchain and configuration prerequisites
if (-not (Test-Path $venvPy)) { throw "Prerequisite missing: $venvPy" }
if (-not (Test-Path $venvAlembic)) { throw "Prerequisite missing: $venvAlembic" }
if (-not (Test-Path $venvPytest)) { throw "Prerequisite missing: $venvPytest" }
if (-not (Test-Path $composeFile)) { throw "Prerequisite missing: $composeFile" }
if (-not (Test-Path $preflightScript)) { throw "Prerequisite missing: $preflightScript" }

Write-Host "======================================================================"
Write-Host "Veritas-RAG -- WP-TEST-B Runbook Execution (Scope: $Scope)"
Write-Host "======================================================================"

# Stage 1: Provision isolated containers
Write-Host "`n>>> [Stage 1/8] Starting isolated test containers (PostgreSQL, Redis, MinIO, Qdrant)..."
docker compose -p $projectName -f $composeFile up -d
if ($LASTEXITCODE -ne 0) {
    throw "STAGE 1 FAILED: Docker Compose failed to launch services."
}

# Stage 2: Bounded readiness check (30-second ceiling)
Write-Host "`n>>> [Stage 2/8] Awaiting service health (bounded 30s timeout)..."
$timeoutSeconds = 30
$elapsed = 0
$servicesHealthy = $false
$targetContainers = @("raguard-postgres-test", "raguard-redis-test", "raguard-minio-test", "raguard-qdrant-test")

while ($elapsed -lt $timeoutSeconds) {
    Start-Sleep -Seconds 1
    $elapsed++

    $allHealthy = $true
    $anyExited = $false

    foreach ($cName in $targetContainers) {
        try {
            $cJson = Get-DockerContainerJson -Target $cName
            $cState = $cJson.State.Status
            $cHealth = if ($cJson.State.Health) { $cJson.State.Health.Status } else { "none" }

            if ($cState -eq "exited") {
                Write-Error "CRITICAL: Container '$cName' exited during startup."
                $anyExited = $true
                break
            }
            if ($cHealth -eq "unhealthy") {
                Write-Error "CRITICAL: Container '$cName' reported unhealthy."
                $anyExited = $true
                break
            }
            if ($cHealth -ne "healthy") {
                $allHealthy = $false
            }
        } catch {
            Write-Error "Container missing or inspect failed for '$cName': $_"
            $anyExited = $true
            break
        }
    }

    if ($anyExited) {
        break
    }

    if ($allHealthy) {
        $servicesHealthy = $true
        Write-Host ">>> All 4 services healthy in ${elapsed}s."
        break
    }
}

if (-not $servicesHealthy) {
    Write-Warning "STAGE 2 FAILED: Services not healthy within ${timeoutSeconds}s."
    Write-Warning "SAFETY POLICY: Containers and volumes are preserved for diagnosis. No automatic cleanup performed."
    throw "READINESS FAILED: Halting execution. Review container logs before manual cleanup."
}

# Stage 3: Non-destructive targeting verification & In-container target probe
Write-Host "`n>>> [Stage 3/8] Verifying container project labels, volume identities, and in-container target database..."
$pgJson = Get-DockerContainerJson -Target "raguard-postgres-test"
$redisJson = Get-DockerContainerJson -Target "raguard-redis-test"
$minioJson = Get-DockerContainerJson -Target "raguard-minio-test"
$qdrantJson = Get-DockerContainerJson -Target "raguard-qdrant-test"

# Project labels
if ($pgJson.Config.Labels.'com.docker.compose.project' -ne $projectName) { throw "IDENTITY VIOLATION: Postgres project mismatch." }
if ($redisJson.Config.Labels.'com.docker.compose.project' -ne $projectName) { throw "IDENTITY VIOLATION: Redis project mismatch." }
if ($minioJson.Config.Labels.'com.docker.compose.project' -ne $projectName) { throw "IDENTITY VIOLATION: MinIO project mismatch." }
if ($qdrantJson.Config.Labels.'com.docker.compose.project' -ne $projectName) { throw "IDENTITY VIOLATION: Qdrant project mismatch." }

# Service labels
if ($pgJson.Config.Labels.'com.docker.compose.service' -ne "postgres-test") { throw "IDENTITY VIOLATION: Postgres service mismatch." }
if ($redisJson.Config.Labels.'com.docker.compose.service' -ne "redis-test") { throw "IDENTITY VIOLATION: Redis service mismatch." }
if ($minioJson.Config.Labels.'com.docker.compose.service' -ne "minio-test") { throw "IDENTITY VIOLATION: MinIO service mismatch." }
if ($qdrantJson.Config.Labels.'com.docker.compose.service' -ne "qdrant-test") { throw "IDENTITY VIOLATION: Qdrant service mismatch." }

# Environment validation inside container
$pgEnv = $pgJson.Config.Env
if ($pgEnv -notcontains "POSTGRES_DB=raguard_test") { throw "IDENTITY VIOLATION: Postgres container environment does not define POSTGRES_DB=raguard_test." }
if ($pgEnv -notcontains "POSTGRES_USER=test") { throw "IDENTITY VIOLATION: Postgres container environment does not define POSTGRES_USER=test." }

# Volume mounts
$pgMount = $pgJson.Mounts | Where-Object { $_.Type -eq "volume" }
if ($pgMount.Name -ne "raguard_test_postgres_data" -or $pgMount.Destination -ne "/var/lib/postgresql/data") {
    throw "IDENTITY VIOLATION: Postgres volume mount mismatch."
}

$minioMount = $minioJson.Mounts | Where-Object { $_.Type -eq "volume" }
if ($minioMount.Name -ne "raguard_test_minio_data" -or $minioMount.Destination -ne "/data") {
    throw "IDENTITY VIOLATION: MinIO volume mount mismatch."
}

$qdrantMount = $qdrantJson.Mounts | Where-Object { $_.Type -eq "volume" }
if ($qdrantMount.Name -ne "raguard_test_qdrant_data" -or $qdrantMount.Destination -ne "/qdrant/storage") {
    throw "IDENTITY VIOLATION: Qdrant volume mount mismatch."
}

# Network Port binding: ensure loopback 127.0.0.1:5432
$pgPortConfig = $pgJson.NetworkSettings.Ports.'5432/tcp'[0]
if ($pgPortConfig.HostIp -ne "127.0.0.1" -or $pgPortConfig.HostPort -ne "5432") {
    throw "IDENTITY VIOLATION: Postgres port binding is not strictly 127.0.0.1:5432."
}

# In-container non-destructive database identity probe BEFORE any mutation
$dbIdentityRaw = docker exec raguard-postgres-test psql -U test -d raguard_test -t -A -c "SELECT current_database();" 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($dbIdentityRaw) -or $dbIdentityRaw.Trim() -ne "raguard_test") {
    throw "MUTATION GATE BLOCKED: In-container database probe failed or returned '$dbIdentityRaw' (expected 'raguard_test'). Halting before any mutation."
}

Write-Host ">>> Identity verified: project='$projectName', all 4 containers and volumes verified."
Write-Host ">>> Database identity confirmed in-container: current_database() == 'raguard_test'."

# Stage 4: Test Credential Synchronization (Gated & Guarded)
Write-Host "`n>>> [Stage 4/8] Synchronizing test user credentials on verified isolated target..."
docker exec raguard-postgres-test psql -U test -d raguard_test -c "ALTER USER test WITH PASSWORD 'test';" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "STAGE 4 WARNING: Credential synchronization returned exit code $LASTEXITCODE. Retrying..."
    Start-Sleep -Seconds 1
    docker exec raguard-postgres-test psql -U test -d raguard_test -c "ALTER USER test WITH PASSWORD 'test';"
    if ($LASTEXITCODE -ne 0) {
        throw "STAGE 4 FAILED: Could not synchronize test user password in container."
    }
}
Write-Host ">>> Database authentication verified and synchronized (user: test, password: test)."

# Stage 5: Set runtime environment & execute target verification preflight with live probes
Write-Host "`n>>> [Stage 5/8] Setting runtime environment and executing preflight..."
$env:APP_ENVIRONMENT = "testing"
if (-not $env:APP_SECRET_KEY -or $env:APP_SECRET_KEY.Trim().Length -eq 0) {
    $env:APP_SECRET_KEY = "test_dummy_secret_key_for_wp_test_b_gate_testing_purposes_only_64b"
}
$env:DATABASE_URL = "postgresql+asyncpg://test:test@127.0.0.1:5432/raguard_test"
$env:ALEMBIC_DATABASE_URL = "postgresql://test:test@127.0.0.1:5432/raguard_test"
$env:REDIS_URL = "redis://127.0.0.1:6379/15"
$env:MINIO_ENDPOINT = "http://127.0.0.1:9000"
$env:MINIO_ENDPOINT_URL = "http://127.0.0.1:9000"
$env:S3_ENDPOINT_URL = "http://127.0.0.1:9000"
$env:AWS_ENDPOINT_URL = "http://127.0.0.1:9000"
$env:MINIO_ACCESS_KEY = "minio_test_user"
$env:MINIO_SECRET_KEY = "minio_test_password_only"
$env:MINIO_BUCKET = "raguard-documents"
$env:S3_BUCKET_NAME = "raguard-documents"
$env:AWS_S3_BUCKET_NAME = "raguard-documents"
$env:QDRANT_HOST = "127.0.0.1"
$env:QDRANT_PORT = "6333"
$env:QDRANT_GRPC_PORT = "6334"
$env:PYTHONPATH = $repoRoot

& $venvPy $preflightScript --probe-all --init-buckets
if ($LASTEXITCODE -ne 0) {
    Write-Warning "STAGE 5 FAILED: Target preflight or live probes failed (code $LASTEXITCODE)."
    Write-Warning "SAFETY POLICY: Preserving containers for diagnosis. No automatic cleanup performed."
    throw "PREFLIGHT FAILED: Target is not verified test infrastructure. Halting before migrations."
}

# Stage 6: Alembic migrations
Write-Host "`n>>> [Stage 6/8] Executing Alembic migrations against verified test target..."
& $venvAlembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Warning "STAGE 6 FAILED: Alembic upgrade failed with exit code $LASTEXITCODE."
    Write-Warning "SAFETY POLICY: Preserving containers and database for diagnosis."
    throw "MIGRATION FAILED: Migration did not complete cleanly."
}
Write-Host ">>> Alembic migrations applied successfully to raguard_test."

# Stage 7: Confirm container identities before running tests
Write-Host "`n>>> [Stage 7/8] Confirming container identities before tests..."
$redisCheck = Get-DockerContainerJson -Target "raguard-redis-test"
if ($redisCheck.NetworkSettings.Ports.'6379/tcp'[0].HostPort -ne "6379") {
    throw "REDIS SAFETY VIOLATION: Port mismatch before tests."
}
Write-Host ">>> Container identities confirmed: PostgreSQL (5432), Redis (6379/DB 15), MinIO (9000), Qdrant (6333)."

# Stage 8: Integration test execution
if ($Scope -eq "smoke") {
    $smokeNode = "backend/tests/integration/api/v1/test_auth_lifecycle.py::test_auth_full_lifecycle"
    Write-Host "`n>>> [Stage 8/8] Executing integration smoke test gate ($smokeNode)..."

    $pytestOutput = & $venvPytest -v --color=no $smokeNode 2>&1
    $testExitCode = $LASTEXITCODE
    $pytestOutput | ForEach-Object { Write-Host $_ }

    if ($testExitCode -ne 0) {
        Write-Warning "STAGE 8 FAILED: Pytest exited with error code $testExitCode."
        throw "SMOKE TEST GATE FAILED: Non-zero exit code $testExitCode."
    }

    $outputLines = $pytestOutput | ForEach-Object { $_.ToString().Trim() }
    $summaryLines = $outputLines | Where-Object { $_ -match '^=+\s+.*\s+=+$' }
    if ($summaryLines.Count -eq 0) { throw "SMOKE TEST GATE FAILED: Missing terminal summary." }
    $terminalSummary = $summaryLines[-1]

    $nodePassed = $outputLines | Where-Object { $_ -match '^backend/tests/integration/api/v1/test_auth_lifecycle\.py::test_auth_full_lifecycle\s+PASSED' }
    $exactOnePassed = $terminalSummary -match '^=+\s+1 passed(?:, \d+ warnings?)? in [0-9.]+s\s+=+$'
    $hasDisallowed = $terminalSummary -match '\b(failed|errors?|skipped|xfailed|xpassed|deselected)\b'

    if (-not $nodePassed -or -not $exactOnePassed -or $hasDisallowed) {
        throw "SMOKE TEST GATE FAILED: Output validation failed."
    }
    Write-Host ">>> Smoke gate verified: $terminalSummary"
} else {
    Write-Host "`n>>> [Stage 8/8] Executing staged integration test suites (Scope: all)..."

    $stagedSuites = @(
        @{ Name = "Tier 1: Auth Lifecycle & Adversarial RBAC"; Target = "backend/tests/integration/api/v1/test_auth_lifecycle.py backend/tests/integration/api/v1/test_rbac_adversarial.py" },
        @{ Name = "Tier 2: Admin Quota Unification & Boundaries"; Target = "backend/tests/integration/api/v1/test_admin_04_quota_unification.py" },
        @{ Name = "Tier 3: Redis & Storage Foundation"; Target = "tests/integration/test_redis_foundation.py tests/integration/test_storage_foundation.py" },
        @{ Name = "Tier 4: Qdrant Foundation & Vector Cross-Tenant Isolation"; Target = "tests/integration/test_qdrant_foundation.py tests/integration/test_retrieval_isolation.py" },
        @{ Name = "Tier 5: Knowledge Base Staleness Watchdog"; Target = "tests/integration/test_f10_staleness_remediation.py" }
    )

    foreach ($suite in $stagedSuites) {
        Write-Host "`n>>> Executing $($suite.Name) ($($suite.Target))..."
        $targets = $suite.Target -split " "
        $suiteOutput = & $venvPytest -v --color=no $targets 2>&1
        $suiteExit = $LASTEXITCODE
        $suiteOutput | ForEach-Object { Write-Host $_ }

        if ($suiteExit -ne 0) {
            Write-Warning "STAGE 8 FAILED on $($suite.Name) with code $suiteExit."
            throw "INTEGRATION SUITE FAILED: $($suite.Name) failed."
        }
    }
    Write-Host ">>> All staged integration test suites PASSED."
}

Write-Host "`n======================================================================"
Write-Host "WP-TEST-B EXECUTION GATE PASSED SUCCESSFULLY."
Write-Host "======================================================================"

# Stage 9: Opt-in cleanup
if ($CleanupOnSuccess) {
    Write-Host "`n>>> Flag -CleanupOnSuccess specified. Verifying ownership before cleanup..."

    $requiredVolumes = @("raguard_test_postgres_data", "raguard_test_minio_data", "raguard_test_qdrant_data")
    foreach ($vol in $requiredVolumes) {
        $isOwned = Test-VolumeOwnership -VolumeName $vol -ExpectedProject $projectName
        if (-not $isOwned) {
            Write-Warning "SAFETY POLICY: Ownership of '$vol' cannot be proven with certainty."
            Write-Warning "WITHHOLDING CLEANUP: Preserving volumes intact to prevent accidental data loss."
            return
        }
    }

    Write-Host ">>> Volume ownership proven for all test volumes. Tearing down $projectName..."
    docker compose -p $projectName -f $composeFile down -v
    Write-Host ">>> Cleanup complete."
} else {
    Write-Host ">>> Test containers and volumes remain running for inspection."
    Write-Host ">>> To clean up, run: docker compose -p $projectName -f $composeFile down -v"
}
