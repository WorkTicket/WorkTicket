<#
.SYNOPSIS
  Drain database connections by service type for maintenance.
.DESCRIPTION
  Queries PgBouncer pg_stat_activity to identify and optionally
  terminate connections by service type (api, celery, beat).
  Supports graceful drain with timeout.
.PARAMETER PgHost
  PostgreSQL host (default: localhost)
.PARAMETER PgPort
  PostgreSQL port (default: 5432)
.PARAMETER PgUser
  PostgreSQL user (default: postgres)
.PARAMETER PgPassword
  PostgreSQL password
.PARAMETER Service
  Service type to drain: api, celery, beat, or all (default: all)
.PARAMETER Timeout
  Max seconds to wait for graceful drain (default: 30)
.PARAMETER Force
  If set, force-kill connections after timeout
.EXAMPLE
  .\drain-connections.ps1 -Service celery -Timeout 60 -Force
#>

param(
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "",
    [ValidateSet("api", "celery", "beat", "all")]
    [string]$Service = "all",
    [int]$Timeout = 30,
    [switch]$Force
)

$conn = "host=$PgHost port=$PgPort user=$PgUser dbname=workticket"
if ($PgPassword) { $conn += " password=$PgPassword" }

$appNameFilter = switch ($Service) {
    "api" { "workticket-api" }
    "celery" { "workticket-celery" }
    "beat" { "workticket-beat" }
    "all" { "workticket-" }
}

function Get-Connections {
    $query = @"
SELECT pid, application_name, state, usename, query_start, wait_event
FROM pg_stat_activity
WHERE application_name LIKE '%$appNameFilter%'
  AND pid <> pg_backend_pid()
ORDER BY query_start;
"@
    & "psql" "$conn" -t -A -F "|" -c $query 2>$null
}

function Kill-Connection {
    param([string]$Pid)
    & "psql" "$conn" -c "SELECT pg_terminate_backend($Pid);" 2>$null
}

Write-Host "Draining $Service connections (filter: $appNameFilter)..."
Write-Host "Timeout: ${Timeout}s" + $(if ($Force) { " [FORCE enabled]" } else { "" })

$conns = Get-Connections
$count = ($conns | Measure-Object -Line).Lines
Write-Host "Active connections: $count"

if ($count -eq 0) {
    Write-Host "No connections to drain"
    exit 0
}

# Wait for graceful drain
if ($Timeout -gt 0) {
    Write-Host "Waiting ${Timeout}s for connections to close naturally..."
    Start-Sleep -Seconds $Timeout
}

$remaining = Get-Connections
$remCount = ($remaining | Measure-Object -Line).Lines

if ($remCount -gt 0 -and $Force) {
    Write-Host "Force-killing $remCount remaining connection(s)..."
    foreach ($line in $remaining) {
        $pid = ($line -split "\|")[0]
        if ($pid -match "^\d+$") {
            Kill-Connection -Pid $pid
            Write-Host "  Killed PID $pid"
        }
    }
} elseif ($remCount -gt 0) {
    Write-Warning "$remCount connection(s) still active — use -Force to terminate"
    exit 1
}

Write-Host "Drain complete"
exit 0
