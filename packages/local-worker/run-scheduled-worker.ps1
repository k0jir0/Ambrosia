[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$WorkerPath,
    [Parameter(Mandatory)] [string]$ConfigurationPath,
    [Parameter(Mandatory)] [string]$CredentialPath
)

$ErrorActionPreference = 'Stop'
$configuration = Get-Content -LiteralPath $ConfigurationPath -Raw | ConvertFrom-Json
$credential = Import-Clixml -LiteralPath $CredentialPath
$token = [System.Net.NetworkCredential]::new('', $credential).Password
if (-not $token) { throw 'The protected Ambrosia worker credential is empty.' }

$env:AMBROSIA_API_URL = [string]$configuration.apiUrl
$env:AMBROSIA_WORKER_TOKEN = $token
$env:OLLAMA_MODEL = [string]$configuration.model
$env:OLLAMA_CONTEXT_LENGTH = [string]$configuration.contextLength
$env:OLLAMA_MAX_OUTPUT_TOKENS = [string]$configuration.maxOutputTokens
$env:OLLAMA_URL = 'http://127.0.0.1:11434'

try {
    & ([string]$configuration.pythonExecutable) $WorkerPath
    if ($LASTEXITCODE -ne 0) { throw "Worker exited with code $LASTEXITCODE" }
}
finally {
    $env:AMBROSIA_WORKER_TOKEN = $null
    $token = $null
}
