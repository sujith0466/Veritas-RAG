# ==============================================================================
# VERITAS-RAG — P0-3 E2E Test Execution Harness (PowerShell)
# ==============================================================================
# Enforces complete fail-closed isolation using a dedicated Docker Compose project.
# Dedicated ports: PostgreSQL (5433), Redis (6389), Qdrant (6343/6344).
# Target database: raguard_test_db.
# ==============================================================================

param (
    [string]$RunId = "",
    [switch]$KeepContainers = $false,
    [switch]$Execute = $false,  # Disabled by default during corrective audit
    [switch]$ChatOnly = $false  # When set, skips lifecycle suite and executes only chat suite
)

$ErrorActionPreference = "Stop"

# Guard: Keep live execution disabled during corrective audit unless explicitly authorized
if (-not $Execute) {
    Write-Host "=========================================================="
    Write-Host "Veritas-RAG P0-3 E2E Test Harness (Corrective Audit Mode)"
    Write-Host "=========================================================="
    Write-Host "Service startup and E2E execution are disabled during audit."
    Write-Host "To execute once authorized, supply the -Execute switch."
    exit 0
}

if (-not $RunId) {
    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $randomSuffix = [System.Guid]::NewGuid().ToString("N").Substring(0, 6)
    $RunId = "e2e_${timestamp}_${randomSuffix}"
}

$ComposeProject = "raguard-e2e-$RunId"
$ComposeFile = "tests/e2e/docker-compose.e2e.yml"
$StorageDir = (Resolve-Path "scratch").Path + "\e2e_storage_$RunId"

# Safety Guard 1: Ensure Compose Project strictly matches expected isolated pattern
if ($ComposeProject -notmatch "^raguard-e2e-e2e_\d+_[0-9a-fA-F]+$") {
    throw "FATAL SAFETY VIOLATION: Refusing to operate on non-standard project name: '$ComposeProject'"
}

# Safety Guard 2: Never target the development Compose project
if ($ComposeProject -eq "raguard" -or $ComposeProject -like "*dev*") {
    throw "FATAL SAFETY VIOLATION: Attempted to target development project: '$ComposeProject'"
}

# Safety Guard 3: Compute canonical source digest and verify dedicated E2E image provenance
$manifestDigestRaw = & ".\venv\Scripts\python.exe" tests/e2e/manifest.py digest
if ($LASTEXITCODE -ne 0 -or -not $manifestDigestRaw) {
    throw "FATAL: Failed to calculate canonical source manifest digest."
}
$sourceDigest = $manifestDigestRaw.Trim()
$expectedImage = "veritas-rag:e2e-$sourceDigest"

Write-Host "Expected E2E Image: $expectedImage (Source Digest: $sourceDigest)"
$imageRaw = docker image inspect $expectedImage 2>$null
if ($LASTEXITCODE -ne 0 -or -not $imageRaw) {
    throw "FATAL: Required E2E image '$expectedImage' not found in local Docker daemon. The image must be built from the current verified source snapshot before execution."
}
$imageObj = $imageRaw | ConvertFrom-Json
$imageId = $imageObj[0].Id
if (-not $imageId -or $imageId -notmatch "^sha256:[0-9a-fA-F]{64}$") {
    throw "FATAL: Image '$expectedImage' does not have a valid cryptographic sha256 image ID. Got: '$imageId'"
}

$imageLabels = $imageObj[0].Config.Labels
if (-not $imageLabels -or -not $imageLabels."veritas.rag.source_digest") {
    throw "FATAL: Image '$expectedImage' is missing required provenance label 'veritas.rag.source_digest'."
}
if ($imageLabels."veritas.rag.source_digest" -ne $sourceDigest) {
    throw "FATAL IMAGE PROVENANCE MISMATCH: Image digest '$($imageLabels."veritas.rag.source_digest")' does not match source digest '$sourceDigest'."
}
Write-Host "Verified image provenance: $expectedImage matches current working tree source snapshot."
Write-Host "Captured Immutable Image ID: $imageId"

# Bind worker environment variables to verified image tag, image ID, and source digest
$env:E2E_WORKER_IMAGE = $expectedImage
$env:E2E_WORKER_IMAGE_ID = $imageId
$env:E2E_SOURCE_DIGEST = $sourceDigest

# Safety Guard 4: Collision detection for containers and volumes
$existingContainers = docker ps -a --filter "name=raguard-e2e-.*-$RunId" --format "{{.Names}}"
if ($existingContainers) {
    throw "FATAL COLLISION DETECTED: Existing containers found for RunId '$RunId': $existingContainers"
}
$existingVolumes = docker volume ls --filter "name=e2e_.*_$RunId" --format "{{.Name}}"
if ($existingVolumes) {
    throw "FATAL COLLISION DETECTED: Existing volumes found for RunId '$RunId': $existingVolumes"
}

# Safety Guard 5: Check all dedicated host ports before startup
$requiredPorts = @(5433, 6389, 6343, 6344, 8008)
foreach ($p in $requiredPorts) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
        $listener.Start()
        $listener.Stop()
    } catch {
        throw "FATAL PORT COLLISION: Dedicated E2E host port $p is already bound or in use. Refusing execution: $_"
    }
}

Write-Host "=========================================================="
Write-Host "Starting Veritas-RAG P0-3 E2E Lifecycle Verification"
Write-Host "Run ID:          $RunId"
Write-Host "Compose Project: $ComposeProject"
Write-Host "Compose File:    $ComposeFile"
Write-Host "Storage Dir:     $StorageDir"
Write-Host "=========================================================="

# Ensure scratch directory exists
if (-not (Test-Path $StorageDir)) {
    New-Item -ItemType Directory -Path $StorageDir -Force | Out-Null
}

# Export environment variables for Compose and Pytest runner
$env:RUN_ID = $RunId
$env:COMPOSE_PROJECT_NAME = $ComposeProject
$env:E2E_POSTGRES_PORT = "5433"
$env:E2E_REDIS_PORT = "6389"
$env:E2E_QDRANT_PORT = "6343"
$env:E2E_QDRANT_GRPC_PORT = "6344"
$env:E2E_API_PORT = "8008"
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/raguard_test_db"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/raguard_test_db"
$env:ALEMBIC_DATABASE_URL = "postgresql://postgres:postgres@localhost:5433/raguard_test_db"
$env:CELERY_BROKER_URL = "redis://localhost:6389/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:6389/1"
$env:REDIS_URL = "redis://localhost:6389/0"
$env:QDRANT_HOST = "localhost"
$env:QDRANT_PORT = "6343"
$env:QDRANT_GRPC_PORT = "6344"
$env:QDRANT_COLLECTION_PREFIX = "raguard_e2e_$RunId"
$env:LOCAL_STORAGE_ROOT = $StorageDir
$env:DEFAULT_EMBEDDING_PROVIDER = "local"

# Pass through LLM provider credentials to Compose if present in .env
$envFile = Join-Path $PSScriptRoot "..\..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim()
            if ($k -eq "OPENROUTER_API_KEY" -and -not $env:OPENROUTER_API_KEY) {
                $env:OPENROUTER_API_KEY = $v
            }
            if ($k -eq "GEMINI_API_KEY" -and -not $env:GEMINI_API_KEY) {
                $env:GEMINI_API_KEY = $v
            }
        }
    }
}
# Pre-seed local embedding model into container-accessible storage directory if available on host
$hostHfModel = Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2"
$targetHfHub = Join-Path $StorageDir "hf_cache\hub"
if (Test-Path $hostHfModel) {
    $targetModelDir = Join-Path $targetHfHub "models--sentence-transformers--all-MiniLM-L6-v2"
    if (-not (Test-Path $targetModelDir)) {
        New-Item -ItemType Directory -Path $targetHfHub -Force | Out-Null
        Copy-Item -Path $hostHfModel -Destination $targetHfHub -Recurse -Force
        Write-Host "Pre-seeded local embedding model cache from host to '$targetModelDir'."
    }
}

$exitCode = 0

try {
    Write-Host "`n[1/4] Starting isolated E2E containers on dedicated ports..."
    docker compose -p $ComposeProject -f $ComposeFile up -d --wait
    if ($LASTEXITCODE -ne 0) {
        throw "FATAL: Failed to start isolated E2E Docker Compose project."
    }

    # Verify running worker container is bound to the exact verified immutable image ID
    $workerContainerName = "raguard-e2e-worker-$RunId"
    Write-Host "Verifying running worker container '$workerContainerName' image ID..."
    $runningWorkerImageId = (docker inspect --format '{{.Image}}' $workerContainerName 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $runningWorkerImageId) {
        throw "FATAL: Failed to inspect image of running worker container '$workerContainerName'."
    }
    $runningWorkerImageId = $runningWorkerImageId.Trim()
    if ($runningWorkerImageId -ne $imageId) {
        throw "FATAL IMAGE ID MISMATCH: Worker container is running image '$runningWorkerImageId', expected immutable image ID '$imageId'."
    }
    Write-Host "Verified worker container '$workerContainerName' is running verified immutable image ID: $imageId"

    # Verify running API container is bound to the exact verified immutable image ID
    $apiContainerName = "raguard-e2e-api-$RunId"
    Write-Host "Verifying running API container '$apiContainerName' image ID..."
    $runningApiImageId = (docker inspect --format '{{.Image}}' $apiContainerName 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $runningApiImageId) {
        throw "FATAL: Failed to inspect image of running API container '$apiContainerName'."
    }
    $runningApiImageId = $runningApiImageId.Trim()
    if ($runningApiImageId -ne $imageId) {
        throw "FATAL IMAGE ID MISMATCH: API container is running image '$runningApiImageId', expected immutable image ID '$imageId'."
    }
    Write-Host "Verified API container '$apiContainerName' is running verified immutable image ID: $imageId"

    Write-Host "`n[2/4] Applying Alembic schema migrations on isolated raguard_test_db..."
    docker exec "raguard-e2e-worker-$RunId" alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "FATAL: Alembic schema migration failed with exit code $LASTEXITCODE. Aborting E2E run immediately."
    }

    $lifecycleExitCode = 0
    if (-not $ChatOnly) {
        Write-Host "`n[3/4] Executing P0-3 Live E2E Lifecycle Pytest Suite..."
        $env:PYTHONPATH = "."
        .\venv\Scripts\pytest tests/e2e/test_p0_3_lifecycle_e2e.py -v --capture=no
        $lifecycleExitCode = $LASTEXITCODE
    } else {
        Write-Host "`n[3/4] Skipping Lifecycle Suite (-ChatOnly specified)..."
    }

    Write-Host "`n[3.5/4] Executing P0-3 Live E2E Chat Integration Pytest Suite..."
    .\venv\Scripts\pytest tests/e2e/test_p0_3_chat_e2e.py -v --capture=no
    $chatExitCode = $LASTEXITCODE

    if ($lifecycleExitCode -ne 0) {
        $exitCode = $lifecycleExitCode
    } elseif ($chatExitCode -ne 0) {
        $exitCode = $chatExitCode
    }
}
catch {
    Write-Error "E2E Execution Failed: $_"
    if ($exitCode -eq 0) {
        $exitCode = 1
    }
}
finally {
    if (-not $KeepContainers) {
        Write-Host "`n[4/4] Tearing down isolated E2E Compose project..."
        try {
            # Step A: Stop worker and API processes before resource cleanup to prevent active writes
            $workerExists = docker ps -a -q --filter "name=^raguard-e2e-worker-$RunId$"
            if ($workerExists) {
                Write-Host "Stopping worker container 'raguard-e2e-worker-$RunId'..."
                docker stop "raguard-e2e-worker-$RunId" | Out-Null
            }
            $apiExists = docker ps -a -q --filter "name=^raguard-e2e-api-$RunId$"
            if ($apiExists) {
                Write-Host "Stopping API container 'raguard-e2e-api-$RunId'..."
                docker stop "raguard-e2e-api-$RunId" | Out-Null
            }

            # Step B: Teardown Compose project and dedicated volumes if any were created
            $projectContainers = docker ps -a -q --filter "name=^raguard-e2e-.*-$RunId$"
            $projectVolumes = docker volume ls -q --filter "name=^e2e_.*_$RunId$"
            if ($projectContainers -or $projectVolumes) {
                Write-Host "Tearing down Compose project '$ComposeProject'..."
                docker compose -p $ComposeProject -f $ComposeFile down -v --remove-orphans
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to cleanly tear down Compose project '$ComposeProject'."
                }
            }

            # Step C: Purge run-specific storage directory
            if (Test-Path $StorageDir) {
                Remove-Item -Path $StorageDir -Recurse -Force -ErrorAction Stop
            }
        }
        catch {
            Write-Error "Teardown error: $_"
            if ($exitCode -eq 0) {
                $exitCode = 1  # Treat cleanup failure as a failed run only if test didn't already fail
            }
        }
    } else {
        Write-Host "`nSkipping container and storage teardown as -KeepContainers switch was supplied."
    }
}

Write-Host "`nE2E Run completed with exit code: $exitCode"
exit $exitCode
