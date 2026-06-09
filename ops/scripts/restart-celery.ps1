<#
.SYNOPSIS
  Restart Celery workers and beat with graceful shutdown.
.DESCRIPTION
  Scales down Celery services, waits for running tasks to complete
  (up to timeout), then re-scales. Also restarts the beat scheduler.
.PARAMETER Project
  Docker Compose project name (default: workticket)
.PARAMETER Timeout
  Max seconds to wait for graceful shutdown (default: 60)
.PARAMETER SkipBeat
  If set, skip restarting the beat scheduler
.EXAMPLE
  .\restart-celery.ps1 -Project workticket -Timeout 120
#>

param(
    [string]$Project = "workticket",
    [int]$Timeout = 60,
    [switch]$SkipBeat
)

$ErrorActionPreference = "Stop"

function Log { param([string]$Msg) Write-Host "[$(Get-Date -Format HH:mm:ss)] $Msg" }

Log "Starting Celery restart for project: $Project"

# Step 1: Stop accepting new tasks (scale to 0)
Log "Scaling worker to 0..."
docker compose -p $Project scale celery_worker=0

# Step 2: Wait for running tasks to finish
$waited = 0
while ($waited -lt $Timeout) {
    $active = docker exec "$($Project)-celery-worker-1" celery -A celery_app inspect active 2>$null
    $reserved = docker exec "$($Project)-celery-worker-1" celery -A celery_app inspect reserved 2>$null
    if (-not $active -and -not $reserved) { break }
    Log "Waiting for tasks to complete (${waited}s)..."
    Start-Sleep -Seconds 5
    $waited += 5
}

if ($waited -ge $Timeout) {
    Write-Warning "Timeout reached — forcing shutdown"
    docker compose -p $Project kill celery_worker
}

# Step 3: Restart beat
if (-not $SkipBeat) {
    Log "Restarting beat scheduler..."
    docker compose -p $Project stop celery_beat
    docker compose -p $Project rm -f celery_beat
    docker compose -p $Project up -d celery_beat
}

# Step 4: Scale workers back up
Log "Scaling worker back up..."
docker compose -p $Project scale celery_worker=5

# Step 5: Verify
Start-Sleep -Seconds 5
$status = docker compose -p $Project ps celery_worker
Log "Worker status:"
$status

Log "Celery restart complete"
