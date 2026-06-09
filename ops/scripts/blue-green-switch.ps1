#Requires -Version 5.1
<#
.SYNOPSIS
    Switch traffic between blue and green environments with health validation.
.DESCRIPTION
    Automates the blue/green traffic switch by swapping nginx upstream
    configuration and reloading nginx. Before switching, it validates that
    the target environment passes all health-gate checks (livez, healthz,
    readyz, beta-gate). After switching, it monitors the target for a
    configurable observation window.

    Designed to work alongside docker-compose.blue-green.yml where backend
    services are duplicated with -blue and -green suffixes on separate ports.
.PARAMETER TargetColor
    The colour to switch traffic TO: "blue" or "green" (required).
.PARAMETER ComposeFile
    Path to the docker-compose.blue-green.yml file (default:
    <RepoRoot>\src\docker-compose.blue-green.yml).
.PARAMETER ApiPort
    Port on localhost that the target backend listens on. Auto-detects:
    blue = 8000, green = 8001. Override if non-standard.
.PARAMETER NginxContainer
    Name of the nginx container (default: workticket-nginx-1).
.PARAMETER NginxConfDir
    Path to the nginx conf.d directory containing blue.conf and green.conf
    (default: <RepoRoot>\src\nginx\conf.d).
.PARAMETER ObservationSeconds
    How many seconds to monitor the target after switching (default: 300 = 5 min).
.PARAMETER CheckInterval
    Seconds between health checks during observation (default: 10).
.PARAMETER SkipHealthGate
    Skip health-gate validation before switching (dangerous).
.PARAMETER DryRun
    Print what would be done without making changes.
.EXAMPLE
    .\blue-green-switch.ps1 -TargetColor green
    .\blue-green-switch.ps1 -TargetColor blue -ObservationSeconds 120
    .\blue-green-switch.ps1 -TargetColor green -DryRun
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("blue", "green")]
    [string]$TargetColor,

    [string]$ComposeFile = "",
    [int]$ApiPort = 0,
    [string]$NginxContainer = "workticket-nginx-1",
    [string]$NginxConfDir = "",
    [int]$ObservationSeconds = 300,
    [int]$CheckInterval = 10,
    [switch]$SkipHealthGate,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Path resolution
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

if (-not $ComposeFile) {
    $ComposeFile = Join-Path $RepoRoot "src\docker-compose.blue-green.yml"
}
if (-not $NginxConfDir) {
    $NginxConfDir = Join-Path $RepoRoot "src\nginx\conf.d"
}
if ($ApiPort -eq 0) {
    $ApiPort = if ($TargetColor -eq "blue") { 8000 } else { 8001 }
}
$FadingColor = if ($TargetColor -eq "blue") { "green" } else { "blue" }
$ActiveConfFile = Join-Path $NginxConfDir "active-upstream.conf"
$TargetConfFile = Join-Path $NginxConfDir "$TargetColor.conf"
$FadingConfFile = Join-Path $NginxConfDir "$FadingColor.conf"

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
function Write-Step($Label) { Write-Host "`n=== $Label ===" -ForegroundColor Cyan }
function Write-Pass  { Write-Host "  PASS" -ForegroundColor Green }
function Write-Fail  { Write-Host "  FAIL" -ForegroundColor Red; $script:FailCount++ }
function Write-Warn  { Write-Host "  WARN" -ForegroundColor Yellow }

$script:FailCount = 0

function Invoke-HealthCheck {
    param(
        [string]$Endpoint,
        [string]$Label,
        [int]$TimeoutSec = 5
    )
    $url = "http://localhost:$ApiPort/$Endpoint"
    try {
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host "    $Label ($url): 200" -ForegroundColor Gray
            return $true
        } else {
            Write-Host "    $Label ($url): $($resp.StatusCode)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "    $Label ($url): FAILED ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

function Assert-HealthGate {
    Write-Step "Health-gate validation for $TargetColor (port $ApiPort)"
    $allPassed = $true

    if (-not (Invoke-HealthCheck -Endpoint "livez" -Label "livez"))   { $allPassed = $false; Write-Fail }
    if (-not (Invoke-HealthCheck -Endpoint "healthz" -Label "healthz")) { $allPassed = $false; Write-Fail }
    if (-not (Invoke-HealthCheck -Endpoint "readyz" -Label "readyz")) { $allPassed = $false; Write-Fail }
    if (-not (Invoke-HealthCheck -Endpoint "beta-gate" -Label "beta-gate")) { $allPassed = $false; Write-Fail }

    # Check SLO endpoint
    try {
        $sloResp = Invoke-RestMethod -Uri "http://localhost:$ApiPort/api/v1/slo" -TimeoutSec 5
        if ($sloResp.availability -gt 0.99) {
            Write-Host "    SLO availability: $($sloResp.availability) (OK)" -ForegroundColor Gray
        } else {
            Write-Host "    SLO availability: $($sloResp.availability) (BELOW 0.99)" -ForegroundColor Red
            $allPassed = $false
            Write-Fail
        }
    } catch {
        Write-Host "    SLO check failed: $_" -ForegroundColor Red
        $allPassed = $false
        Write-Fail
    }

    if (-not $allPassed) {
        Write-Host "`n*** Health-gate FAILED for $TargetColor. Aborting switch. ***" -ForegroundColor Red
        exit 1
    }
    Write-Host "`n  All health gates passed." -ForegroundColor Green
}

function Switch-NginxUpstream {
    param([string]$SourceConf, [string]$Desc)

    Write-Step "Switching nginx upstream to $Desc"

    # Validate config files
    if (-not (Test-Path $SourceConf)) {
        Write-Host "  ERROR: Upstream config not found: $SourceConf" -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path $NginxConfDir)) {
        Write-Host "  ERROR: nginx conf.d directory not found: $NginxConfDir" -ForegroundColor Red
        exit 1
    }

    if ($DryRun) {
        Write-Host "  [DRY RUN] Would copy: $SourceConf -> $ActiveConfFile" -ForegroundColor Gray
        Write-Host "  [DRY RUN] Would run: docker exec $NginxContainer nginx -s reload" -ForegroundColor Gray
        return
    }

    # Copy the target config as active
    Copy-Item -Path $SourceConf -Destination $ActiveConfFile -Force
    Write-Host "  Upstream config set to: $Desc" -ForegroundColor Gray

    # Test nginx config before reloading
    $testResult = docker exec $NginxContainer nginx -t 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: nginx config test failed. Restoring previous config." -ForegroundColor Red
        Write-Host "  $testResult" -ForegroundColor Red
        # Restore the fading colour config to be safe
        Copy-Item -Path $FadingConfFile -Destination $ActiveConfFile -Force
        exit 1
    }
    Write-Host "  nginx -t: OK" -ForegroundColor Gray

    # Reload nginx gracefully
    docker exec $NginxContainer nginx -s reload
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: nginx reload failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  nginx reloaded: traffic now flowing to $Desc" -ForegroundColor Green
}

function Start-ObservationWindow {
    Write-Step "Observation window: ${ObservationSeconds}s (check every ${CheckInterval}s)"

    $iterations = [math]::Floor($ObservationSeconds / $CheckInterval)
    $errors = 0
    $maxErrors = 3

    for ($i = 1; $i -le $iterations; $i++) {
        $ts = Get-Date -Format "HH:mm:ss"
        $statusLine = "[$i/$iterations $ts]"

        try {
            $livezOk = Invoke-HealthCheck -Endpoint "livez" -Label "livez"
            $healthzOk = Invoke-HealthCheck -Endpoint "healthz" -Label "healthz"
            $readyzOk = Invoke-HealthCheck -Endpoint "readyz" -Label "readyz"

            if (-not $livezOk -or -not $healthzOk -or -not $readyzOk) {
                $errors++
                Write-Host "  $statusLine HEALTH CHECK FAILURE ($errors/$maxErrors consecutive)" -ForegroundColor Red
            } else {
                $errors = 0
                Write-Host "  $statusLine All endpoints OK" -ForegroundColor DarkGray
            }

            if ($errors -ge $maxErrors) {
                Write-Host "`n*** $maxErrors consecutive health failures — OBSERVATION FAILED ***" -ForegroundColor Red
                Write-Host "  Consider rolling back: .\blue-green-switch.ps1 -TargetColor $FadingColor" -ForegroundColor Yellow
                exit 1
            }
        } catch {
            $errors++
            Write-Host "  $statusLine ERROR: $_" -ForegroundColor Red
            if ($errors -ge $maxErrors) {
                Write-Host "`n*** Observation failed after $maxErrors consecutive errors ***" -ForegroundColor Red
                exit 1
            }
        }

        if ($i -lt $iterations) {
            Start-Sleep -Seconds $CheckInterval
        }
    }

    Write-Host "`n  Observation window complete — $TargetColor is healthy." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Host "=== Blue/Green Traffic Switch ===" -ForegroundColor Cyan
Write-Host "  Target:   $TargetColor (port $ApiPort)" -ForegroundColor Gray
Write-Host "  Fading:   $FadingColor" -ForegroundColor Gray
Write-Host "  Compose:  $ComposeFile" -ForegroundColor Gray
Write-Host "  Nginx:    $NginxContainer" -ForegroundColor Gray
Write-Host "  Observe:  ${ObservationSeconds}s" -ForegroundColor Gray
if ($DryRun) {
    Write-Host "  MODE:     DRY RUN" -ForegroundColor Yellow
}
if ($SkipHealthGate) {
    Write-Host "  WARNING:  Health-gate validation SKIPPED" -ForegroundColor Yellow
}

# 1. Health-gate check on target before switching
if (-not $SkipHealthGate) {
    Assert-HealthGate
}

# 2. Switch nginx upstream to target colour
Switch-NginxUpstream -SourceConf $TargetConfFile -Desc $TargetColor

# 3. Wait briefly for nginx to propagate
Write-Host "`n  Waiting 3s for nginx reload to settle..." -ForegroundColor Gray
if (-not $DryRun) {
    Start-Sleep -Seconds 3
}

# 4. Quick post-switch verification
Write-Step "Post-switch quick check"
$postLiveOk = Invoke-HealthCheck -Endpoint "livez" -Label "livez"
$postHealthOk = Invoke-HealthCheck -Endpoint "healthz" -Label "healthz"
if (-not $postLiveOk -or -not $postHealthOk) {
    Write-Host "`n*** Post-switch check FAILED — rolling back immediately ***" -ForegroundColor Red
    Switch-NginxUpstream -SourceConf $FadingConfFile -Desc $FadingColor
    exit 1
}
Write-Pass

# 5. Observation window
if (-not $DryRun) {
    Start-ObservationWindow
} else {
    Write-Host "`n  [DRY RUN] Would monitor $TargetColor for ${ObservationSeconds}s" -ForegroundColor Gray
}

# 6. Summary
Write-Step "Switch Summary"
Write-Host "  Traffic is now flowing to: $TargetColor" -ForegroundColor Green
Write-Host "  $FadingColor is idle and should remain running for 10 minutes" -ForegroundColor Yellow
Write-Host "  To rollback: .\blue-green-switch.ps1 -TargetColor $FadingColor" -ForegroundColor Gray
Write-Host ""
Write-Host "  After the 10-minute keep-blue window, drain and remove $FadingColor:" -ForegroundColor Gray
Write-Host "    docker compose -f $ComposeFile stop backend-$FadingColor celery-worker-$FadingColor celery-beat-$FadingColor" -ForegroundColor Gray
Write-Host "    .\ops\scripts\drain-connections.ps1 -Service celery -Timeout 240 -Force" -ForegroundColor Gray

if ($script:FailCount -gt 0) {
    Write-Host "`n*** Switch completed with warnings. Review before removing $FadingColor. ***" -ForegroundColor Yellow
    exit 2
}

Write-Host "`n*** Switch to $TargetColor complete. ***" -ForegroundColor Green
exit 0
