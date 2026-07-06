Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

python -m pip install --upgrade pip build
python -m build packages/sdk-python
python -m build packages/cli

if (-not (Test-Path artifacts)) {
    New-Item -ItemType Directory -Path artifacts | Out-Null
}

$hashLines = @()
Get-ChildItem packages/sdk-python/dist/*.whl, packages/cli/dist/*.whl | ForEach-Object {
    $hash = Get-FileHash $_.FullName -Algorithm SHA256
    $hashLines += "$($hash.Hash.ToLower())  $($_.FullName.Replace($RootDir + '\\', '').Replace('\\', '/'))"
}
$hashLines | Set-Content -Path artifacts/release-checksums.sha256 -Encoding utf8

python -m pip install --force-reinstall packages/sdk-python/dist/*.whl
python -m pip install --force-reinstall packages/cli/dist/*.whl

ambrosia --help | Out-Null

Write-Host "Reproducible CLI install completed."
Write-Host "Checksums: artifacts/release-checksums.sha256"
