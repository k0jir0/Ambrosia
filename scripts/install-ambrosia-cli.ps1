param(
    [switch]$AddToPath,
    [switch]$LaunchMenu,
    [switch]$Distribution,
    [switch]$BuildDistribution,
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$CliDir = Join-Path $RepoRoot "packages\cli"
$DistDir = Join-Path $RepoRoot "dist\ambrosia-cli"
if (-not $InstallDir) {
    $InstallDir = Join-Path $RepoRoot ".local\ambrosia-cli"
}

function Add-DirectoryToUserPath {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $paths = @($currentPath -split ";" | Where-Object { $_ })
    if ($paths -notcontains $Directory) {
        $newPath = if ($currentPath) { "$currentPath;$Directory" } else { $Directory }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "Added Ambrosia CLI to user PATH: $Directory"
        Write-Host "Open a new terminal before running 'ambrosia' from any directory."
    } else {
        Write-Host "Ambrosia CLI is already on user PATH."
    }
}

if (-not (Test-Path $CliDir)) {
    throw "Ambrosia CLI directory not found: $CliDir"
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    throw "uv is not installed or not on PATH. Install it from https://docs.astral.sh/uv/"
}

if ($Distribution) {
    if ($BuildDistribution) {
        & (Join-Path $PSScriptRoot "build-ambrosia-cli.ps1")
    }

    if (-not (Test-Path $DistDir)) {
        throw "Distribution directory not found: $DistDir. Run scripts\build-ambrosia-cli.ps1 or pass -BuildDistribution."
    }

    $cliWheel = Get-ChildItem $DistDir -Filter "ambrosia_cli-*.whl" | Select-Object -First 1
    $sdkWheel = Get-ChildItem $DistDir -Filter "ambrosia_sdk-*.whl" | Select-Object -First 1
    if (-not $cliWheel -or -not $sdkWheel) {
        throw "Missing Ambrosia CLI/SDK wheels in $DistDir. Run scripts\build-ambrosia-cli.ps1."
    }

    Write-Host "Creating isolated Ambrosia CLI environment: $InstallDir"
    uv venv $InstallDir
    $python = Join-Path $InstallDir "Scripts\python.exe"
    $scripts = Join-Path $InstallDir "Scripts"

    Write-Host "Installing Ambrosia CLI from local distribution artifacts..."
    uv pip install --python $python --find-links $DistDir ambrosia-cli==0.1.0

    if ($AddToPath) {
        Add-DirectoryToUserPath -Directory $scripts
    }

    Write-Host "Ambrosia CLI installed from local distribution."
    Write-Host "Run: $scripts\ambrosia.exe commands list"

    if ($LaunchMenu) {
        & (Join-Path $scripts "ambrosia.exe") commands list
    }
    exit 0
}

$CliScriptsDir = Join-Path $CliDir ".venv\Scripts"

Push-Location $CliDir
try {
    Write-Host "Installing Ambrosia CLI environment..."
    uv sync

    if ($AddToPath) {
        Add-DirectoryToUserPath -Directory $CliScriptsDir
    }

    Write-Host "Ambrosia CLI installed."
    Write-Host "Run: ambrosia commands list"

    if ($LaunchMenu) {
        uv run ambrosia commands list
    }
}
finally {
    Pop-Location
}
