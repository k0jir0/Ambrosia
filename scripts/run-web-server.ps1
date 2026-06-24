param(
  [string]$WebRoot,
  [string]$NextCli,
  [string]$Port,
  [string]$LogFile,
  [string]$ErrorLogFile
)

$ErrorActionPreference = "Stop"

Set-Location $WebRoot

if (-not (Test-Path (Split-Path -Parent $LogFile))) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) | Out-Null
}

& node $NextCli start --hostname 0.0.0.0 --port $Port 1>> $LogFile 2>> $ErrorLogFile
