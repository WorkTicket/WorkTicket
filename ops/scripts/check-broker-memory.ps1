<#
.SYNOPSIS
  Check Redis broker memory usage and alert if approaching maxmemory.
.DESCRIPTION
  Connects to the broker Redis instance and reports current memory usage
  vs maxmemory. Exits with code 1 if usage exceeds 80%.
.PARAMETER Host
  Redis host (default: localhost)
.PARAMETER Port
  Redis port (default: 6379)
.PARAMETER Password
  Redis password (optional)
.PARAMETER WarnThreshold
  Warning threshold as fraction of maxmemory (default: 0.80)
.EXAMPLE
  .\check-broker-memory.ps1 -Host redis-broker -Port 6379
#>

param(
    [string]$Host = "localhost",
    [int]$Port = 6379,
    [string]$Password = "",
    [double]$WarnThreshold = 0.80
)

if (-not (Get-Command "redis-cli" -ErrorAction SilentlyContinue)) {
    Write-Error "redis-cli not found in PATH. Install Redis CLI or run from a system where it is available."
    exit 1
}

$info = if ($Password) {
    redis-cli -h $Host -p $Port -a $Password INFO memory
} else {
    redis-cli -h $Host -p $Port INFO memory
}

$used = 0
$max = 0

foreach ($line in $info) {
    if ($line -match "^used_memory:(\d+)$") { $used = [long]$matches[1] }
    if ($line -match "^maxmemory:(\d+)$") { $max = [long]$matches[1] }
}

if ($max -eq 0) {
    Write-Warning "maxmemory not set on broker Redis — OOM risk"
    exit 2
}

$pct = [double]$used / $max
Write-Host "Redis broker memory: $([math]::Round($used / 1MB, 1))MB / $([math]::Round($max / 1MB, 1))MB ($([math]::Round($pct * 100, 1))%)"

if ($pct -ge $WarnThreshold) {
    Write-Warning "Memory usage exceeds ${WarnThreshold:P0} threshold — alerting"
    exit 1
}

Write-Host "OK — memory within limits"
exit 0
