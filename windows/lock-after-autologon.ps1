# lock-after-autologon.ps1 - lock the screen right after Windows signs in by itself
#
# Windows is set to sign in automatically, so the server, the tunnels and the
# Discord bot all come back after a reboot without anyone at the keyboard.
# This runs at logon from Task Scheduler and locks the desktop straight away;
# everything started at logon keeps running behind the lock screen.
#
# It only locks shortly after Windows started. Signing out and back in by hand
# later in the day is someone at the keyboard, not the automatic sign-in.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$WithinMinutes = 5,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $LogPath) { $LogPath = Join-Path $scriptDir 'lock-after-autologon.log' }

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    try {
        if ((Test-Path $LogPath) -and ((Get-Item $LogPath).Length -gt 256KB)) {
            Set-Content -Path $LogPath -Value (Get-Content $LogPath -Tail 100) -Encoding UTF8
        }
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch { }
}

$boot   = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$uptime = (Get-Date) - $boot
if ($uptime.TotalMinutes -gt $WithinMinutes) {
    Write-Log ("Signed in {0:N0} min after boot - someone signed in by hand, not locking" -f $uptime.TotalMinutes)
    exit 0
}

if ($PSCmdlet.ShouldProcess('desktop', 'lock')) {
    & (Join-Path $env:SystemRoot 'System32\rundll32.exe') user32.dll,LockWorkStation
    Write-Log ("Locked the desktop {0:N0} s after boot" -f $uptime.TotalSeconds)
}
exit 0
