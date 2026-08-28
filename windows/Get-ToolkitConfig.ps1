# Dot-source this to read the toolkit's config.json from PowerShell:
#
#     . (Join-Path $PSScriptRoot 'Get-ToolkitConfig.ps1')
#     $cfg = Get-ToolkitConfig
#     $backupRoot = Get-ToolkitValue $cfg 'backupDir' 'C:\mc-backup'
#
# The Python side has settings.py; this is the same one-file-to-fill-in idea
# for the scheduled tasks and batch helpers.

function Get-ToolkitConfig {
    param([string]$Path)

    if (-not $Path) {
        if ($env:MC_TOOLKIT_CONFIG) {
            $Path = $env:MC_TOOLKIT_CONFIG
        } else {
            $Path = Join-Path (Split-Path -Parent $PSScriptRoot) 'config.json'
        }
    }
    if (-not (Test-Path $Path)) {
        throw "找不到設定檔：$Path　（請先複製 config.example.json 為 config.json）"
    }
    Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-ToolkitValue {
    <#
        Reads a dotted path out of the config object, falling back to a
        default. Missing intermediate objects are not an error - a partially
        filled config should still start.
    #>
    param(
        [Parameter(Mandatory)] $Config,
        [Parameter(Mandatory)] [string]$Path,
        $Default = $null
    )

    $node = $Config
    foreach ($part in $Path.Split('.')) {
        if ($null -eq $node) { return $Default }
        $prop = $node.PSObject.Properties[$part]
        if (-not $prop) { return $Default }
        $node = $prop.Value
    }
    if ($null -eq $node -or "$node" -eq '') { return $Default }
    return $node
}
