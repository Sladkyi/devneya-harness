param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Connect', 'Start', 'Status')]
    [string]$Action,
    [string]$NodePath = 'node.exe',
    [string]$PreviewRoot = (Join-Path $env:LOCALAPPDATA 'devneya-opencode-browser-preview')
)

$ErrorActionPreference = 'Stop'
$node = (Get-Command $NodePath -CommandType Application | Select-Object -First 1).Source
if ((& $node --version) -ne 'v24.22.0') { throw 'This preview requires Node.js 24.22.0.' }
$root = [IO.Path]::GetFullPath($PreviewRoot)
$app = Join-Path $root 'app'
$state = Join-Path $root 'state'
$console = Join-Path $app 'node_modules/@opencode/console/index.js'
$runtimeEntry = Join-Path $PSScriptRoot '../../runtime/entry.mjs'
$previewBuild = 'opencode-browser-dsh-0.2.2-rc.1-tui-0.20.2'

function Invoke-CheckedNode {
    & $node @args
    if ($LASTEXITCODE -ne 0) { throw "Preview command exited with code $LASTEXITCODE" }
}

if ($Action -eq 'Install') {
    $npm = Join-Path (Split-Path $node) 'node_modules/npm/bin/npm-cli.js'
    if (!(Test-Path -LiteralPath $npm)) { throw 'Use the Node.js distribution that includes npm.' }
    New-Item -ItemType Directory -Force -Path $app | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'package.json'), (Join-Path $PSScriptRoot 'package-lock.json') -Destination $app
    Invoke-CheckedNode $npm --prefix $app ci --strict-peer-deps --omit=dev --include=optional --ignore-scripts --no-fund --no-audit
    Copy-Item -LiteralPath $runtimeEntry -Destination (Join-Path $app 'entry.mjs')
    return
}

if (!(Test-Path -LiteralPath $console) -or !(Test-Path -LiteralPath (Join-Path $app 'entry.mjs'))) {
    throw 'Run the preview Install action first.'
}

$environment = @{
    DEVNEYA_HOME = $state
    DEVNEYA_RUNTIME = $root
    DEVNEYA_BUILD_ID = $previewBuild
    DSH_HOME = (Join-Path $state 'data')
    XDG_DATA_HOME = (Join-Path $state 'console-data')
    XDG_CONFIG_HOME = (Join-Path $state 'console-config')
    XDG_CACHE_HOME = (Join-Path $state 'console-cache')
    OPENCODE_CONSOLE_AUTO_UPDATE = 'off'
    OPENCODE_API_KEY = $null
    OPENCODE_CONSOLE_SERVER = $null
    NODE_OPTIONS = $null
    NODE_PATH = $null
    PATH = (Split-Path $node) + [IO.Path]::PathSeparator + (Join-Path $app 'node_modules/.bin') + [IO.Path]::PathSeparator + $env:PATH
}
$previous = @{}
try {
    foreach ($name in $environment.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $environment[$name], 'Process')
    }
    New-Item -ItemType Directory -Force -Path $env:DSH_HOME | Out-Null
    switch ($Action) {
        'Connect' { Invoke-CheckedNode $console setup deepseek-harness }
        'Status' { Invoke-CheckedNode $console status }
        'Start' { Invoke-CheckedNode (Join-Path $app 'entry.mjs') }
    }
} finally {
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
