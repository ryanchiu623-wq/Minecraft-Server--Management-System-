# mirror-backup.ps1 - keep copies of the newest backups on a second disk
#
# backup-world.ps1 writes to E:, one hard disk. If that disk dies the backups
# go with it, so after a backup that verified, the newest world and config
# zips are copied to backupMirrorDir (another physical disk) and the newest
# keepMirror of each are kept there.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File mirror-backup.ps1
#   powershell -ExecutionPolicy Bypass -File mirror-backup.ps1 -WorldZip E:\mc-backup\world-....zip

[CmdletBinding()]
param(
    [string]$WorldZip,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Get-ToolkitConfig.ps1')
$toolkit    = Get-ToolkitConfig
$backupRoot = Get-ToolkitValue $toolkit 'backupDir' 'E:\mc-backup'
$mirrorDir  = Get-ToolkitValue $toolkit 'backupMirrorDir' ''
$keep       = [int](Get-ToolkitValue $toolkit 'keepMirror' 3)
if (-not $LogPath) { $LogPath = Join-Path $PSScriptRoot 'backup-world.log' }

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} [{1}] mirror: {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    try { Add-Content -Path $LogPath -Value $line -Encoding UTF8 } catch { }
}

if (-not $mirrorDir) { exit 0 }
if (-not (Test-Path (Split-Path -Qualifier $mirrorDir))) {
    Write-Log "$mirrorDir is not available - no second copy this time" 'WARN'
    exit 1
}
if (-not (Test-Path $mirrorDir)) { New-Item -ItemType Directory -Path $mirrorDir | Out-Null }

if (-not $WorldZip) {
    $WorldZip = Get-ChildItem $backupRoot -Filter 'world-*.zip' | Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
$configZip = Get-ChildItem $backupRoot -Filter 'config-*.zip' | Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 -ExpandProperty FullName

$failed = $false
foreach ($src in @($WorldZip, $configZip) | Where-Object { $_ }) {
    $dest = Join-Path $mirrorDir (Split-Path -Leaf $src)
    if ((Test-Path $dest) -and (Get-Item $dest).Length -eq (Get-Item $src).Length) { continue }
    # Copy under a temporary name, so a copy cut short never looks complete.
    $part = "$dest.part"
    try {
        Copy-Item $src $part -Force
        if ((Get-Item $part).Length -ne (Get-Item $src).Length) { throw 'size differs after copy' }
        Move-Item $part $dest -Force
        Write-Log "Copied $(Split-Path -Leaf $src) to $mirrorDir"
    } catch {
        Remove-Item $part -Force -ErrorAction SilentlyContinue
        Write-Log "Could not copy $(Split-Path -Leaf $src): $($_.Exception.Message)" 'WARN'
        $failed = $true
    }
}

foreach ($pattern in 'world-*.zip', 'config-*.zip') {
    Get-ChildItem $mirrorDir -Filter $pattern | Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $keep | ForEach-Object {
            Remove-Item $_.FullName -Force
            Write-Log "Removed old copy $($_.Name)"
        }
}
if ($failed) { exit 1 }
exit 0
