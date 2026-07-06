$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$CliDir = Join-Path $RepoRoot "packages\cli"
$ExeDistDir = Join-Path $RepoRoot "dist\ambrosia-cli-exe"
$WorkDir = Join-Path $RepoRoot ".local\pyinstaller-work"
$SpecDir = Join-Path $RepoRoot ".local\pyinstaller-spec"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not installed or not on PATH. Install it from https://docs.astral.sh/uv/"
}

if (-not (Test-Path $CliDir)) {
    throw "Ambrosia CLI directory not found: $CliDir"
}

New-Item -ItemType Directory -Force -Path $ExeDistDir, $WorkDir, $SpecDir | Out-Null

Push-Location $CliDir
try {
    Write-Host "Ensuring Ambrosia CLI environment is synced..."
    uv sync

    Write-Host "Building single-file Ambrosia CLI executable..."
    uv run --with pyinstaller pyinstaller `
        --onefile `
        --name ambrosia `
        --distpath $ExeDistDir `
        --workpath $WorkDir `
        --specpath $SpecDir `
        ambrosia_cli\main.py
}
finally {
    Pop-Location
}

$ExePath = Join-Path $ExeDistDir "ambrosia.exe"
if (-not (Test-Path $ExePath)) {
    throw "Expected executable was not created: $ExePath"
}

Write-Host "Built Ambrosia CLI executable: $ExePath"
& $ExePath --version
