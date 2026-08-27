# sync-map.ps1 - upload the rendered BlueMap web folder to Cloudflare Pages
#
# BlueMap keeps the BlueMap web directory up to date as chunks change; this
# script pushes that folder to a Cloudflare Pages project. Wrangler hashes
# every file and only uploads the ones that actually changed, so running
# this on a schedule is cheap.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File sync-map.ps1
#   powershell -ExecutionPolicy Bypass -File sync-map.ps1 -WhatIf   (dry run)
#
# Config lives in sync-map.config.json next to this script.
# The API token is NOT stored there - it is read from the file named by
# "tokenFile". Keep that file out of any shared or synced folder.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ConfigPath,
    [string]$LogPath
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is empty inside param() defaults on Windows PowerShell 5.1,
# which is what Task Scheduler runs - resolve the script folder here instead.
$scriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
} else {
    Split-Path -Parent $MyInvocation.MyCommand.Definition
}
if (-not $ConfigPath) { $ConfigPath = Join-Path $scriptDir 'sync-map.config.json' }
if (-not $LogPath)    { $LogPath    = Join-Path $scriptDir 'sync-map.log' }

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    try {
        if ((Test-Path $LogPath) -and ((Get-Item $LogPath).Length -gt 1MB)) {
            Set-Content -Path $LogPath -Value (Get-Content $LogPath -Tail 200) -Encoding UTF8
        }
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch {
        # Logging must never take the sync down.
    }
}

# ---- load config -------------------------------------------------------
if (-not (Test-Path $ConfigPath)) {
    Write-Log "Config not found: $ConfigPath" 'ERROR'
    exit 1
}
$cfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json

foreach ($key in @('projectName', 'accountId', 'tokenFile', 'webDir')) {
    if ([string]::IsNullOrWhiteSpace($cfg.$key)) {
        Write-Log "Config is missing required field: $key" 'ERROR'
        exit 1
    }
}

if (-not (Test-Path $cfg.webDir)) {
    Write-Log "Web directory not found: $($cfg.webDir)" 'ERROR'
    exit 1
}
if (-not (Test-Path $cfg.tokenFile)) {
    Write-Log "Token file not found: $($cfg.tokenFile)" 'ERROR'
    exit 1
}
$token = (Get-Content $cfg.tokenFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($token)) {
    Write-Log "Token file is empty: $($cfg.tokenFile)" 'ERROR'
    exit 1
}

# Call wrangler's JS entry point through node directly. The npm-generated
# shims (wrangler.cmd / wrangler.ps1) hang when driven from a non-interactive
# PowerShell session, which is exactly how Task Scheduler runs this.
$node = (Get-Command node -ErrorAction SilentlyContinue)
if (-not $node) {
    Write-Log 'node not found in PATH - is Node.js installed?' 'ERROR'
    exit 1
}
$wranglerJs = Join-Path $env:APPDATA 'npm/node_modules/wrangler/bin/wrangler.js'
if (-not (Test-Path $wranglerJs)) {
    Write-Log "wrangler not found at $wranglerJs - run: npm install -g wrangler" 'ERROR'
    exit 1
}

# ---- do the work -------------------------------------------------------
$fileCount = (Get-ChildItem $cfg.webDir -Recurse -File).Count
$sizeMB    = [math]::Round(((Get-ChildItem $cfg.webDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Log "Deploying $($cfg.webDir) ($fileCount files, $sizeMB MB) to Pages project '$($cfg.projectName)'"

if (-not $PSCmdlet.ShouldProcess($cfg.projectName, "Deploy $fileCount files")) {
    Write-Log 'Dry run: nothing uploaded'
    exit 0
}

# Credentials go to the child process only - never into the machine environment.
$env:CLOUDFLARE_API_TOKEN  = $token
$env:CLOUDFLARE_ACCOUNT_ID = $cfg.accountId
# Without these wrangler can stop on an interactive prompt, which would hang
# forever when this runs unattended from Task Scheduler.
$env:CI                    = 'true'
$env:WRANGLER_SEND_METRICS = 'false'

# Wrangler writes temp files into the current directory. If that happens to sit
# under a Controlled-Folder-Access protected path (Documents), Defender blocks
# the write and wrangler hangs forever - so pin the working directory here.
Push-Location $scriptDir

try {
    $output = & $node.Source $wranglerJs pages deploy $cfg.webDir `
        --project-name $cfg.projectName `
        --commit-dirty=true 2>&1
    $code = $LASTEXITCODE

    foreach ($line in $output) {
        $text = "$line"
        if ($text.Trim()) { Write-Log "  wrangler: $text" }
    }

    if ($code -ne 0) {
        Write-Log "wrangler exited with code $code" 'ERROR'
        exit 1
    }
    Write-Log 'Deploy finished'
    exit 0

} catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1

} finally {
    Pop-Location
    Remove-Item Env:\CLOUDFLARE_API_TOKEN  -ErrorAction SilentlyContinue
    Remove-Item Env:\CLOUDFLARE_ACCOUNT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:\CI                    -ErrorAction SilentlyContinue
    Remove-Item Env:\WRANGLER_SEND_METRICS -ErrorAction SilentlyContinue
}
