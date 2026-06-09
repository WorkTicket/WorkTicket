<#
.SYNOPSIS
    Rollback WorkTicket deployment to a previous version.
.DESCRIPTION
    Performs a controlled rollback of the WorkTicket backend stack to a
    specified previous version. Supports full and partial rollbacks.
.PARAMETER TargetVersion
    The Docker image tag to roll back to (required).
.PARAMETER RollbackMigration
    If set, runs alembic downgrade to the previous migration.
.PARAMETER SkipWorkerRestart
    If set, skips restarting Celery workers (only restarts API + beat).
.PARAMETER DryRun
    If set, prints what would be done without making changes.
.EXAMPLE
    .\rollback.ps1 -TargetVersion "v1.0.0-beta.9"
    .\rollback.ps1 -TargetVersion "v1.0.0-beta.9" -RollbackMigration
    .\rollback.ps1 -TargetVersion "v1.0.0-beta.9" -DryRun
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$TargetVersion,

    [switch]$RollbackMigration,
    [switch]$SkipWorkerRestart,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$COMPOSE_DIR = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$COMPOSE_DIR = Join-Path $COMPOSE_DIR "src"

Write-Host "=== WorkTicket Rollback to $TargetVersion ===" -ForegroundColor Cyan
Write-Host "Compose directory: $COMPOSE_DIR"
if ($DryRun) {
    Write-Host "=== DRY RUN MODE ===" -ForegroundColor Yellow
}

# 1. Verify target version exists
$imageName = "workticket-backend:$TargetVersion"
Write-Host "[1/6] Verifying image $imageName exists..." -ForegroundColor Green
if (-not $DryRun) {
    $check = docker image inspect $imageName 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Image $imageName not found locally. Attempting pull..." -ForegroundColor Yellow
        docker pull $imageName
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to pull image $imageName. Aborting rollback."
            exit 1
        }
    }
}

Push-Location $COMPOSE_DIR
try {
    # 2. Remove current tasks from queues (drain)
    Write-Host "[2/6] Draining Celery queues..." -ForegroundColor Green
    if (-not $DryRun) {
        & docker compose exec -T celery-beat celery -A celery_app control cancel_feed 2>&1 | Out-Null
    }

    # 3. Roll back the API
    Write-Host "[3/6] Rolling back API backend..." -ForegroundColor Green
    if (-not $DryRun) {
        $env:WORKTICKET_BACKEND_TAG = $TargetVersion
        & docker compose up -d --force-recreate backend
        Write-Host "Waiting for backend to be ready..." -ForegroundColor Yellow
        $ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            try {
                $resp = Invoke-WebRequest -Uri "http://localhost:8000/readyz" -TimeoutSec 2 -UseBasicParsing
                if ($resp.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            } catch {}
            Start-Sleep -Seconds 2
        }
        if (-not $ready) {
            Write-Error "Backend did not become healthy within 60s. Check logs: docker compose logs backend"
            exit 1
        }
        Write-Host "Backend is healthy." -ForegroundColor Green
    }

    # 4. Rollback database migration
    if ($RollbackMigration) {
        Write-Host "[4/6] Rolling back database migration..." -ForegroundColor Green
        if (-not $DryRun) {
            & docker compose exec -T backend alembic downgrade -1
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Database migration rollback failed. Check logs."
                exit 1
            }
            Write-Host "Database migration rolled back." -ForegroundColor Green
        }
    } else {
        Write-Host "[4/6] Skipping database migration rollback (use -RollbackMigration to enable)" -ForegroundColor Gray
    }

    # 5. Restart Celery workers
    if (-not $SkipWorkerRestart) {
        Write-Host "[5/6] Restarting Celery workers..." -ForegroundColor Green
        $workerServices = @(
            "celery-beat",
            "celery-worker-default",
            "celery-worker-ai_text",
            "celery-worker-ai_audio",
            "celery-worker-ai_image"
        )
        foreach ($svc in $workerServices) {
            Write-Host "  Restarting $svc..." -ForegroundColor Yellow
            if (-not $DryRun) {
                & docker compose up -d --force-recreate $svc
                Start-Sleep -Seconds 5
            }
        }
    } else {
        Write-Host "[5/6] Skipping Celery worker restart" -ForegroundColor Gray
    }

    # 6. Post-rollback verification
    Write-Host "[6/6] Running post-rollback verification..." -ForegroundColor Green
    if (-not $DryRun) {
        Start-Sleep -Seconds 5
        try {
            $livez = Invoke-WebRequest -Uri "http://localhost:8000/livez" -TimeoutSec 5 -UseBasicParsing
            Write-Host "  livez: $($livez.StatusCode)" -ForegroundColor Green
            $healthz = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -TimeoutSec 5 -UseBasicParsing
            Write-Host "  healthz: $($healthz.StatusCode)" -ForegroundColor Green
            $readyz = Invoke-WebRequest -Uri "http://localhost:8000/readyz" -TimeoutSec 5 -UseBasicParsing
            Write-Host "  readyz: $($readyz.StatusCode)" -ForegroundColor Green

            # Verify Celery workers
            $workers = & docker compose exec -T celery-beat celery -A celery_app inspect ping --timeout 10 2>&1
            if ($LASTEXITCODE -eq 0 -and $workers -match "pong") {
                Write-Host "  Celery workers: OK" -ForegroundColor Green
            } else {
                Write-Warning "  Celery workers may not be healthy. Check 'docker compose logs celery-beat'"
            }
        } catch {
            Write-Warning "Post-rollback verification failed: $_"
        }
    }

    Write-Host "=== Rollback to $TargetVersion complete ===" -ForegroundColor Cyan

} finally {
    Pop-Location
}
