# backup-world.ps1 - snapshot the Minecraft world to a rotating set of zips
#
# Flushes the world to disk first, then copies it while auto-saving is paused,
# so the snapshot cannot catch a half-written region file.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File backup-world.ps1
#   powershell -ExecutionPolicy Bypass -File backup-world.ps1 -Keep 14

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$Keep,
    [string]$BackupRoot,
    [string]$LogPath
)

# Defaults come from the toolkit's config.json so a fresh install only edits
# one file; explicit parameters still win.
. (Join-Path $PSScriptRoot 'Get-ToolkitConfig.ps1')
$toolkit = Get-ToolkitConfig
if (-not $Keep)       { $Keep = [int](Get-ToolkitValue $toolkit 'keepBackups' 7) }
if (-not $BackupRoot) { $BackupRoot = Get-ToolkitValue $toolkit 'backupDir' 'E:\mc-backup' }

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $LogPath) { $LogPath = Join-Path $scriptDir 'backup-world.log' }

# The world and the RCON client live with the server, not with this script.
# Resolving them next to the script only works when the toolkit was unpacked
# into the server folder.
$serverDir = Get-ToolkitValue $toolkit 'serverDir' $scriptDir
$worldDir  = Join-Path $serverDir (Get-ToolkitValue $toolkit 'levelName' 'world')
$rconPy    = Join-Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts') 'rcon.py'
if (-not (Test-Path $rconPy)) { $rconPy = Join-Path $scriptDir 'rcon.py' }

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

# A process started from Explorer keeps the PATH Explorer had at logon, so
# right after installing Python a plain "python" is not found from the
# console's backup button. Fall back to the per-user install location.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $python) { $python = 'python' }

function Invoke-Rcon {
    param([string[]]$Commands)
    try {
        $out = & $python $rconPy @Commands 2>&1
        return @{ ok = ($LASTEXITCODE -eq 0); out = ($out -join "`n") }
    } catch {
        return @{ ok = $false; out = $_.Exception.Message }
    }
}

if (-not (Test-Path $worldDir)) {
    Write-Log "World folder not found: $worldDir" 'ERROR'
    exit 1
}

# The server may be stopped - that is fine, the files are already at rest.
$serverUp = [bool](Get-NetTCPConnection -LocalPort 25565 -State Listen -ErrorAction SilentlyContinue)
$stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
$zipPath  = Join-Path $BackupRoot "world-$stamp.zip"

if (-not (Test-Path $BackupRoot)) { New-Item -ItemType Directory -Path $BackupRoot | Out-Null }

Write-Log "Backing up $worldDir (server running: $serverUp)"

if (-not $PSCmdlet.ShouldProcess($worldDir, 'Back up world')) {
    Write-Log 'Dry run: nothing written'
    exit 0
}

$savePaused = $false
try {
    if ($serverUp) {
        # save-off then save-all flush: no writes happen while we copy.
        $r = Invoke-Rcon @('save-off', 'save-all flush')
        if ($r.ok) {
            $savePaused = $true
            Write-Log 'Auto-save paused and world flushed to disk'
        } else {
            Write-Log "RCON failed, backing up live files anyway: $($r.out)" 'WARN'
        }
    }

    # Copy to a staging folder first: zipping straight from a live world folder
    # is slower and more exposed to changes mid-read.
    $staging = Join-Path $env:TEMP "mc-backup-$stamp"
    # session.lock is held exclusively by the running server and is
    # recreated on load, so excluding it avoids a spurious failure.
    $null = robocopy $worldDir $staging /E /COPY:DAT /XF session.lock /R:1 /W:1 /NFL /NDL /NP
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }

} finally {
    # Must always run, and must actually succeed: leaving save-off on would
    # stop the server ever saving again, which is far worse than a failed
    # backup. Retry, and confirm the server said it is enabled.
    if ($savePaused) {
        $resumed = $false
        for ($i = 1; $i -le 5; $i++) {
            $r = Invoke-Rcon @('save-on')
            if ($r.ok -and $r.out -match 'enabled') { $resumed = $true; break }
            Write-Log "save-on attempt $i did not confirm, retrying" 'WARN'
            Start-Sleep -Seconds 3
        }
        if ($resumed) {
            Write-Log 'Auto-save resumed'
        } else {
            Write-Log 'AUTO-SAVE IS STILL OFF - run: python rcon.py "save-on"' 'ERROR'
            # Leave a marker the Discord bot reports, so this cannot go unnoticed.
            # scripts\ is where discord-control.py looks for it.
            $markerDir = Join-Path (Split-Path -Parent $scriptDir) 'scripts'
            if (-not (Test-Path $markerDir)) { $markerDir = $scriptDir }
            Set-Content -Path (Join-Path $markerDir 'SAVE-OFF-WARNING') -Value (Get-Date -Format s) -Encoding ASCII
        }
    }
}

try {
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zipPath -CompressionLevel Optimal -Force
    $sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Log "Wrote $zipPath ($sizeMB MB)"
} finally {
    Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
}

# A backup that cannot be restored is only found out on the day it is needed.
# Open every chunk of the new zip now, while there is still a good older one.
$scriptsDir = Split-Path -Parent $rconPy
$verifyPy   = Join-Path $scriptsDir 'verify-backup.py'
$verified   = $true
if (Test-Path $verifyPy) {
    $out = & $python $verifyPy $zipPath 2>&1
    $verified = ($LASTEXITCODE -eq 0)
    if ($verified) {
        Write-Log "Verified: $(@($out)[-1])"
    } else {
        foreach ($line in @($out) | Select-Object -Last 8) { Write-Log "verify: $line" 'ERROR' }
        Write-Log 'NEW BACKUP FAILED VERIFICATION - older backups are kept' 'ERROR'
        $markerDir = Join-Path (Split-Path -Parent $scriptDir) 'scripts'
        if (-not (Test-Path $markerDir)) { $markerDir = $scriptDir }
        Set-Content -Path (Join-Path $markerDir 'BACKUP-WARNING') -Value $zipPath -Encoding UTF8
    }
}

# Rotation: keep the newest $Keep archives - but only after a backup that
# verified, so a broken one never pushes out the last good one.
$all = Get-ChildItem $BackupRoot -Filter 'world-*.zip' | Sort-Object LastWriteTime -Descending
if ($verified -and $all.Count -gt $Keep) {
    foreach ($old in $all | Select-Object -Skip $Keep) {
        Remove-Item $old.FullName -Force
        Write-Log "Removed old backup $($old.Name)"
    }
}

# Everything else a restore needs: settings, plugin data and jars, the
# toolkit, tunnel credentials. A failure here must not fail the world backup.
$configPy = Join-Path $scriptsDir 'backup-config.py'
if (Test-Path $configPy) {
    $out = & $python $configPy --dest $BackupRoot --keep $Keep 2>&1
    $level = if ($LASTEXITCODE -eq 0) { 'INFO' } else { 'WARN' }
    foreach ($line in @($out)) { Write-Log "config: $line" $level }
}

# A second copy on another physical disk (backupMirrorDir), only of a backup
# that verified. It logs to this same file itself.
$mirrorPs1 = Join-Path $scriptDir 'mirror-backup.ps1'
if ($verified -and (Test-Path $mirrorPs1)) {
    & $mirrorPs1 -WorldZip $zipPath -LogPath $LogPath | Out-Null
}

Write-Log "Done. $([math]::Min($all.Count, $Keep) ) backup(s) kept in $BackupRoot"
exit 0
