#Requires -Version 5.1
<#
.SYNOPSIS
  Deploy production-hardening fixes to staging and run verification checks.
.DESCRIPTION
  Automates the deploy flow for the 17 code fixes across 6 files.
  Validates syntax, runs chaos tests, checks dashboards, and outputs a
  go/no-go decision for production promotion.
.PARAMETER SkipDockerBuild
  Skip docker-compose build step (use pre-built images).
.PARAMETER SkipChaosTests
  Skip running chaos tests after deploy.
#>

param(
  [switch]$SkipDockerBuild,
  [switch]$SkipChaosTests,
  [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LogFile = Join-Path -Path $RepoRoot -ChildPath "logs\deploy-staging-$(Get-Date -Format yyyyMMdd-HHmmss).log"
$null = New-Item -ItemType Directory -Path (Split-Path $LogFile -Parent) -Force
Start-Transcript -Path $LogFile -Append

$Global:PassCount = 0
$Global:FailCount = 0
$Global:WarningCount = 0

function Write-Step($Label) { Write-Host "`n=== $Label ===" -ForegroundColor Cyan }
function Write-Pass  { Write-Host "  PASS" -ForegroundColor Green; $Global:PassCount++ }
function Write-Fail  { Write-Host "  FAIL" -ForegroundColor Red; $Global:FailCount++ }
function Write-Warn  { Write-Host "  WARN" -ForegroundColor Yellow; $Global:WarningCount++ }

# ---------------------------------------------------------------------------
# 1. Pre-deploy validation — file integrity
# ---------------------------------------------------------------------------
Write-Step "Pre-deploy: file integrity and syntax checks"

$ModifiedFiles = @(
  "src\backend\celery_app.py",
  "src\backend\app\billing\concurrency.py",
  "src\backend\app\billing\router.py",
  "src\backend\app\ai\router.py",
  "src\backend\app\config.py",
  "src\docker-compose.yml"
)

$AllExist = $true
foreach ($f in $ModifiedFiles) {
  $Path = Join-Path $RepoRoot $f
  if (Test-Path $Path) {
    Write-Host "  Found: $f" -ForegroundColor Gray
  } else {
    Write-Host "  MISSING: $f" -ForegroundColor Red
    $AllExist = $false
  }
}
if ($AllExist) { Write-Pass } else { Write-Fail }

# Python syntax check on modified .py files
foreach ($f in @("celery_app.py", "concurrency.py", "router.py" -as [string[]])) {
  $Path = Join-Path $RepoRoot "src\backend\app\billing\$f"
  if (!(Test-Path $Path)) { $Path = Join-Path $RepoRoot "src\backend\app\ai\$f" }
  if (!(Test-Path $Path)) { $Path = Join-Path $RepoRoot "src\backend\$f" }
  if (Test-Path $Path) {
    python -m compileall $Path 2>&1 | Out-Null
    if ($?) { Write-Host "  Syntax OK: $f" -ForegroundColor Gray; Write-Pass }
    else    { Write-Host "  SYNTAX ERROR: $f" -ForegroundColor Red; Write-Fail }
  }
}

# Validate JSON dashboard
python -m json.tool (Join-Path $RepoRoot "ops\grafana-dashboards\workticket-overview.json") *>$null
if ($?) { Write-Pass } else { Write-Fail }

# ---------------------------------------------------------------------------
# 2. Build & Deploy
# ---------------------------------------------------------------------------
Write-Step "Build and deploy to staging"

if (-not $WhatIf) {
  Set-Location $RepoRoot

  if (-not $SkipDockerBuild) {
    docker-compose -f src\docker-compose.yml build --no-cache celery worker beat
    if (-not $?) { Write-Fail; throw "Docker build failed" }
    Write-Pass
  }

  docker stack deploy -c src\docker-compose.yml workticket-staging
  if (-not $?) { Write-Fail; throw "Docker stack deploy failed" }
  Write-Pass

  Write-Host "  Waiting 30s for services to stabilize..." -ForegroundColor Gray
  Start-Sleep -Seconds 30
} else {
  Write-Host "  [WhatIf] Would run: docker-compose build + stack deploy" -ForegroundColor Gray
  Write-Warn
}

# ---------------------------------------------------------------------------
# 3. Post-deploy chaos tests
# ---------------------------------------------------------------------------
if (-not $SkipChaosTests -and -not $WhatIf) {
  Write-Step "Post-deploy chaos tests"

  $ChaosTests = @(
    "test_c1_silent_rollback.py",
    "test_c2_stalled_job_recovery.py",
    "test_c3_stripe_webhook.py",
    "test_c4_concurrency_limit.py",
    "test_c5_event_loop_isolation.py",
    "test_h2_idempotency.py",
    "test_h5_queue_backpressure.py",
    "test_h7_ws_global_count.py",
    "test_m1_dlq_fallback.py",
    "test_r1_retry_deadlock.py"
  )

  Set-Location (Join-Path $RepoRoot "chaos")
  foreach ($test in $ChaosTests) {
    Write-Host "  Running $test..." -ForegroundColor Gray
    $output = python $test 2>&1
    $result = $output | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($result -and $result.passed -eq $result.total) {
      Write-Pass
    } else {
      Write-Fail
      $output | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
  }
}

# ---------------------------------------------------------------------------
# 4. Summary
# ---------------------------------------------------------------------------
Write-Step "Deploy Summary"
$Total = $Global:PassCount + $Global:FailCount
Write-Host "  Passed: $($Global:PassCount)/$Total"
Write-Host "  Failed: $($Global:FailCount)/$Total"
Write-Host "  Warnings: $Global:WarningCount"

if ($Global:FailCount -eq 0) {
  Write-Host "`n*** GO: All checks passed. Ready for production validation. ***" -ForegroundColor Green
}
else {
  Write-Host "`n*** NO-GO: $($Global:FailCount) failures — review the log and fix before promoting to production. ***" -ForegroundColor Red
}

Stop-Transcript
