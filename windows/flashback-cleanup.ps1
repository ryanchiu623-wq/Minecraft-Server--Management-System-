# flashback-cleanup.ps1 - delete SimplyFlashback replays and clips older than N hours
#
# Every online player is recorded all the time (scripts/flashback-record.py), so
# replays pile up quickly. The scheduled task "MC Toolkit Flashback Cleanup" runs
# this every hour and keeps about the last 36 hours.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File flashback-cleanup.ps1
#   powershell -ExecutionPolicy Bypass -File flashback-cleanup.ps1 -KeepHours 48 -WhatIf

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$KeepHours,
    [string]$LogPath
)

. (Join-Path $PSScriptRoot 'Get-ToolkitConfig.ps1')
$toolkit = Get-ToolkitConfig
if (-not $KeepHours) { $KeepHours = [int](Get-ToolkitValue $toolkit 'flashback.keepHours' 36) }

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $LogPath) { $LogPath = Join-Path $scriptDir 'flashback-cleanup.log' }

$serverDir = Get-ToolkitValue $toolkit 'serverDir' $scriptDir
$sfDir     = Join-Path $serverDir 'plugins\SimplyFlashback'

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    try {
        if ((Test-Path $LogPath) -and ((Get-Item $LogPath).Length -gt 1MB)) {
            Set-Content -Path $LogPath -Value (Get-Content $LogPath -Tail 200) -Encoding UTF8
        }
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch { }
}

if ($KeepHours -lt 1) {
    Write-Log "KeepHours is $KeepHours - refusing to delete everything" 'ERROR'
    exit 1
}

$cutoff  = (Get-Date).AddHours(-$KeepHours)
$removed = 0
$freed   = 0L

foreach ($tree in 'replays', 'clips') {
    $root = Join-Path $sfDir $tree
    if (-not (Test-Path $root)) { continue }

    # Only finished .flashback files. clips\tmp holds the live ring buffers of
    # players being clipped right now and must be left alone.
    $old = Get-ChildItem $root -Recurse -File -Filter '*.flashback' |
        Where-Object { $_.FullName -notlike (Join-Path $root 'tmp\*') -and $_.LastWriteTime -lt $cutoff }

    foreach ($f in $old) {
        if ($PSCmdlet.ShouldProcess($f.FullName, 'Delete')) {
            try {
                $size = $f.Length
                Remove-Item $f.FullName -Force
                $removed++
                $freed += $size
            } catch {
                Write-Log "Could not delete $($f.FullName): $($_.Exception.Message)" 'WARN'
            }
        }
    }

    # Player folders left empty by the sweep.
    Get-ChildItem $root -Directory | Where-Object { $_.Name -ne 'tmp' } | ForEach-Object {
        if (-not (Get-ChildItem $_.FullName -Recurse -Force | Select-Object -First 1)) {
            if ($PSCmdlet.ShouldProcess($_.FullName, 'Remove empty folder')) {
                Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

if ($removed) {
    Write-Log ("Removed {0} file(s) older than {1} h, freed {2:N1} MB" -f $removed, $KeepHours, ($freed / 1MB))
}
exit 0
