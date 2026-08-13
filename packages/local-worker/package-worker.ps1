[CmdletBinding()]
param(
    [Parameter()]
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'dist'),

    [Parameter()]
    [string]$CertificateThumbprint = ''
)

$ErrorActionPreference = 'Stop'
$workerPath = Join-Path $PSScriptRoot 'ambrosia_local_worker.py'
$readmePath = Join-Path $PSScriptRoot 'README.md'
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
$resolvedRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)

if (-not (Test-Path -LiteralPath $workerPath -PathType Leaf)) {
    throw "Worker source is missing: $workerPath"
}
if ($resolvedOutput -eq $resolvedRoot) {
    throw 'OutputDirectory must not be the worker source directory'
}

New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("ambrosia-worker-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null

try {
    Copy-Item -LiteralPath $workerPath -Destination $stage
    Copy-Item -LiteralPath $readmePath -Destination $stage

    $manifestPath = Join-Path $stage 'MANIFEST.sha256'
    $manifestLines = Get-ChildItem -LiteralPath $stage -File |
        Where-Object Name -ne 'MANIFEST.sha256' |
        Sort-Object Name |
        ForEach-Object {
            $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            "$hash  $($_.Name)"
        }
    [System.IO.File]::WriteAllLines($manifestPath, $manifestLines, [System.Text.UTF8Encoding]::new($false))

    if ($CertificateThumbprint) {
        $catalogPath = Join-Path $stage 'AmbrosiaLocalWorker.cat'
        New-FileCatalog -Path $stage -CatalogFilePath $catalogPath -CatalogVersion 2.0 | Out-Null
        $signature = Set-AuthenticodeSignature -FilePath $catalogPath -Certificate (
            Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
        ) -HashAlgorithm SHA256
        if ($signature.Status -ne 'Valid') {
            throw "Worker catalog signing failed: $($signature.StatusMessage)"
        }
    }

    $zipPath = Join-Path $resolvedOutput 'ambrosia-local-worker.zip'
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath
    }
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -CompressionLevel Optimal

    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumPath = "$zipPath.sha256"
    [System.IO.File]::WriteAllText(
        $checksumPath,
        "$zipHash  $([System.IO.Path]::GetFileName($zipPath))`n",
        [System.Text.UTF8Encoding]::new($false)
    )
    [pscustomobject]@{
        Package = $zipPath
        Checksum = $checksumPath
        Signed = [bool]$CertificateThumbprint
        Sha256 = $zipHash
    }
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
