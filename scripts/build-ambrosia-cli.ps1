$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RepoRoot "dist\ambrosia-cli"
$SdkDir = Join-Path $RepoRoot "packages\sdk-python"
$CliDir = Join-Path $RepoRoot "packages\cli"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not installed or not on PATH. Install it from https://docs.astral.sh/uv/"
}

foreach ($path in @($SdkDir, $CliDir)) {
    if (-not (Test-Path $path)) {
        throw "Required package directory not found: $path"
    }
}

if (Test-Path $DistDir) {
    Remove-Item $DistDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

Push-Location $SdkDir
try {
    Write-Host "Building ambrosia-sdk wheel..."
    uv build --wheel --out-dir $DistDir
}
finally {
    Pop-Location
}

Push-Location $CliDir
try {
    Write-Host "Building ambrosia-cli wheel..."
    uv build --wheel --out-dir $DistDir
}
finally {
    Pop-Location
}

Write-Host "Built Ambrosia CLI distribution artifacts: $DistDir"
Get-ChildItem $DistDir | ForEach-Object { Write-Host " - $($_.Name)" }
