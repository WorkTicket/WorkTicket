<#
.SYNOPSIS
  Rotate DLQ fallback files that exceed size threshold.
.DESCRIPTION
  Scans DLQ fallback directory for files exceeding threshold,
  rotates them with timestamp suffix, and logs actions.
  Designed to run as a cron job / scheduled task.
.PARAMETER DlqDir
  DLQ fallback directory path (default: /var/log/workticket)
.PARAMETER ThresholdMB
  Max file size in MB before rotation (default: 100)
.PARAMETER DryRun
  If set, show what would be rotated without acting
.EXAMPLE
  .\rotate-dlq.ps1 -DlqDir C:\WorkTicket\logs -ThresholdMB 50 -DryRun
#>

param(
    [string]$DlqDir,
    [int]$ThresholdMB = 100,
    [switch]$DryRun
)

# Default path is for Linux Docker deployments. On Windows, set the
# WORKTICKET_DLQ_DIR environment variable to a Windows-appropriate path.
if (-not $DlqDir) {
    if ($env:OS -eq 'Windows_NT') {
        if ($env:WORKTICKET_DLQ_DIR) {
            $DlqDir = $env:WORKTICKET_DLQ_DIR
        } else {
            Write-Warning "WORKTICKET_DLQ_DIR not set — defaulting to /var/log/workticket (Linux path). Set it to a Windows path for this environment."
            $DlqDir = "/var/log/workticket"
        }
    } else {
        $DlqDir = "/var/log/workticket"
    }
}

$ErrorActionPreference = "Stop"
$thresholdBytes = $ThresholdMB * 1MB
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$rotated = 0

Write-Host "Scanning $DlqDir for DLQ files > ${ThresholdMB}MB..."

if (-not (Test-Path -LiteralPath $DlqDir)) {
    Write-Warning "DLQ directory not found: $DlqDir"
    exit 1
}

Get-ChildItem -LiteralPath $DlqDir -Filter "workticket_dlq_fallback*" | ForEach-Object {
    if ($_.Length -gt $thresholdBytes) {
        $rotatedName = "$($_.FullName).$timestamp"
        if ($DryRun) {
            Write-Host "[DRY RUN] Would rotate: $($_.Name) ($([math]::Round($_.Length / 1MB, 1))MB) -> $rotatedName"
        } else {
            Move-Item -LiteralPath $_.FullName -Destination $rotatedName
            Write-Host "Rotated: $($_.Name) -> $rotatedName"
        }
        $rotated++
    }
}

if ($rotated -eq 0) {
    Write-Host "No files exceeded ${ThresholdMB}MB threshold"
} else {
    Write-Host "Rotated $rotated file(s)"
}
