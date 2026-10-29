param(
    [string]$Task = 'd02',
    [ValidateSet('current', 'baseline')][string]$Agent = 'current',
    [switch]$PrepareOnly,
    [switch]$SkipData,
    [switch]$LocalUv,
    [string]$Out = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
$savedUvInstall = $env:UV_UNMANAGED_INSTALL
try {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand -and !$LocalUv) {
        $uvBinary = $uvCommand.Source
    } else {
        $bootstrap = Join-Path $projectRoot '.cache/bootstrap'
        $uvBinary = Join-Path $bootstrap 'uv.exe'
        if (!(Test-Path -LiteralPath $uvBinary)) {
            New-Item -ItemType Directory -Path $bootstrap -Force | Out-Null
            $installer = Join-Path $bootstrap 'install-uv.ps1'
            Invoke-WebRequest -Uri 'https://astral.sh/uv/0.12.9/install.ps1' -OutFile $installer
            $env:UV_UNMANAGED_INSTALL = $bootstrap
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
            if ($LASTEXITCODE -ne 0) { throw 'Local uv bootstrap failed.' }
        }
    }
    & $uvBinary sync --locked --extra test
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    if (!$SkipData) {
        & $uvBinary run --locked agent-trace prepare-data --download
        if ($LASTEXITCODE -ne 0) { throw 'Corpus download or checksum verification failed.' }
    }
    if (!$PrepareOnly) {
        $runArgs = @('run', '--locked', 'agent-trace', 'reproduce', '--task', $Task, '--agent', $Agent, '--trace')
        if ($Out) { $runArgs += @('--out', $Out) }
        & $uvBinary @runArgs
        if ($LASTEXITCODE -ne 0) { throw 'Agent execution failed; inspect the printed report path.' }
    }
} finally {
    $env:UV_UNMANAGED_INSTALL = $savedUvInstall
    Pop-Location
}
