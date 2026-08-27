# sync-loop.ps1 - run the BlueMap -> Cloudflare Pages sync on a loop
#
# Started by start.bat alongside the Minecraft server and killed when the
# server window closes, so the map only syncs while the server is actually
# running (the map cannot change when nobody is playing).
#
# Interval is in minutes; the first sync happens immediately.

[CmdletBinding()]
param(
    [int]$IntervalMinutes = 30
)

$ErrorActionPreference = 'Continue'

# start.bat finds this window by title in order to kill the loop when the
# server stops. PowerShell overwrites whatever title `start` set, so claim it
# back here - otherwise the loop survives the server and keeps syncing.
try { $Host.UI.RawUI.WindowTitle = 'bluemap-sync' } catch { }

$scriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
} else {
    Split-Path -Parent $MyInvocation.MyCommand.Definition
}
$syncScript = Join-Path $scriptDir 'sync-map.ps1'

# Wrangler writes temp files into the current directory; keep it out of any
# Controlled-Folder-Access protected path or it will hang. See sync-map.ps1.
Set-Location $scriptDir

if (-not (Test-Path $syncScript)) {
    Write-Host "sync-map.ps1 not found at $syncScript"
    exit 1
}

Write-Host "BlueMap sync loop started - every $IntervalMinutes minute(s)"
Write-Host 'Close this window (or stop the server) to end the loop.'

while ($true) {
    try {
        & $syncScript
    } catch {
        Write-Host "sync failed: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}
