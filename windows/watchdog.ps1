# watchdog.ps1 - keep the stack alive
#
# Runs every few minutes from Task Scheduler and repairs three things:
#   1. the server, if it died while it was meant to be running
#   2. the playit tunnel, if the server is up but the service is not
#   3. the Discord control bot, if its task stopped
#
# It only restarts the server when start.bat left a "server.running" marker
# behind. A deliberate stop removes that marker, so shutting the server down
# on purpose does not fight the watchdog.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$MaxRestartsPerHour = 3,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $LogPath) { $LogPath = Join-Path $scriptDir 'watchdog.log' }

# The marker, the lock and start.bat belong to the server directory.
# start.bat writes server.running beside itself, so looking for it next to
# this script only works when the toolkit was unpacked into the server folder.
. (Join-Path $PSScriptRoot 'Get-ToolkitConfig.ps1')
try { $toolkit = Get-ToolkitConfig } catch { $toolkit = $null }
$serverDir = if ($toolkit) {
    Get-ToolkitValue $toolkit 'serverDir' $scriptDir
} else { $scriptDir }

$marker    = Join-Path $serverDir 'server.running'
$histFile  = Join-Path $scriptDir 'watchdog-restarts.txt'
$startBat  = Join-Path $serverDir 'start.bat'
$botTask   = 'Minecraft Discord Control Bot'

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    try {
        if ((Test-Path $LogPath) -and ((Get-Item $LogPath).Length -gt 512KB)) {
            Set-Content -Path $LogPath -Value (Get-Content $LogPath -Tail 200) -Encoding UTF8
        }
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch { }
}

function Test-ServerProcess {
    [bool](Get-CimInstance Win32_Process -Filter "Name='java.exe'" -ErrorAction SilentlyContinue |
           Where-Object { $_.CommandLine -like '*paper.jar*' })
}

function Test-RestartInProgress {
    # restart-sequence.py holds this lock between stopping and starting. Time
    # limit so a restart script that died cannot mute the watchdog for good.
    $lock = Join-Path $serverDir 'restart.lock'
    if (-not (Test-Path $lock)) { return $false }
    return (((Get-Date) - (Get-Item $lock).LastWriteTime).TotalMinutes -lt 10)
}

function Test-ServerPort {
    [bool](Get-NetTCPConnection -LocalPort 25565 -State Listen -ErrorAction SilentlyContinue)
}

function Get-RecentRestarts {
    if (-not (Test-Path $histFile)) { return @() }
    $cutoff = (Get-Date).AddHours(-1)
    @(Get-Content $histFile | ForEach-Object {
        try { [datetime]::Parse($_) } catch { $null }
    } | Where-Object { $_ -and $_ -gt $cutoff })
}

$actions = 0

# ---- 1. server -----------------------------------------------------------
if (Test-Path $marker) {
    if (Test-ServerProcess) {
        # Running normally. Nothing to do.
    } elseif (Test-RestartInProgress) {
        # A scheduled restart is between stopping and starting. It brings the
        # server back itself; starting start.bat here would race it - the port
        # is free at that moment, so both instances pass start.bat's guard and
        # one of the two JVMs then dies unable to bind.
        Write-Log 'Scheduled restart in progress - not intervening'
    } else {
        $recent = Get-RecentRestarts
        if ($recent.Count -ge $MaxRestartsPerHour) {
            Write-Log "Server is down but already restarted $($recent.Count) times this hour - not restarting again. Something is wrong; check logs\latest.log and crash-reports\." 'ERROR'
        } elseif ($PSCmdlet.ShouldProcess('Minecraft server', 'restart')) {
            Write-Log 'Server marked as running but no java process found - restarting' 'WARN'
            # The embedded quotes on the title are deliberate. Start-Process does
            # not quote list elements containing spaces, so a bare 'MC Server'
            # reaches cmd as two words: start takes "MC" as the window title and
            # tries to run "Server", and start.bat is never launched at all.
            Start-Process -FilePath 'cmd.exe' `
                -ArgumentList '/c', 'start', '"MC Server"', '/min', $startBat, '/nopause' `
                -WorkingDirectory $scriptDir -WindowStyle Hidden
            Add-Content -Path $histFile -Value (Get-Date -Format s) -Encoding ASCII
            $actions++
            Start-Sleep -Seconds 45
            if (Test-ServerPort) { Write-Log 'Server is back up' } else { Write-Log 'Server still not listening after 45s' 'WARN' }
        }
    }
}

# ---- 2. tunnel -----------------------------------------------------------
# Only meaningful while the server is up: with it down the tunnel is supposed
# to be stopped too.
if (Test-ServerPort) {
    $svc = Get-Service playitd -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Running') {
        if ($PSCmdlet.ShouldProcess('playitd', 'start')) {
            Write-Log 'Server is up but playit is stopped - starting it' 'WARN'
            Start-Service playitd -ErrorAction SilentlyContinue
            $actions++
            Start-Sleep -Seconds 15
            $svc.Refresh()
            Write-Log "playit is now $((Get-Service playitd).Status)"
        }
    }
}

# ---- 3. Discord bot ------------------------------------------------------
$bot = Get-ScheduledTask -TaskName $botTask -ErrorAction SilentlyContinue
if ($bot -and $bot.State -ne 'Running') {
    if ($PSCmdlet.ShouldProcess($botTask, 'start')) {
        Write-Log "Discord bot task is $($bot.State) - starting it" 'WARN'
        Start-ScheduledTask -TaskName $botTask
        $actions++
    }
}

# ---- 4. crash reports ----------------------------------------------------
# Surface crashes rather than letting them pile up unnoticed.
$crashDir = Join-Path $scriptDir 'crash-reports'
if (Test-Path $crashDir) {
    $fresh = Get-ChildItem $crashDir -Filter '*.txt' -ErrorAction SilentlyContinue |
             Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-1) }
    foreach ($c in $fresh) {
        $seen = Join-Path $scriptDir ('crash-seen-' + $c.BaseName + '.flag')
        if (-not (Test-Path $seen)) {
            Write-Log "NEW CRASH REPORT: $($c.Name)" 'ERROR'
            Set-Content -Path $seen -Value (Get-Date -Format s) -Encoding ASCII
            Set-Content -Path (Join-Path $scriptDir 'CRASH-WARNING') -Value $c.Name -Encoding UTF8
        }
    }
}

if ($actions -eq 0) { Write-Log 'All good' }
exit 0
