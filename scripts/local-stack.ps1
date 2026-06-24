param(
  [string]$Command = "serve"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LocalApiScript = Join-Path $PSScriptRoot "local-api.ps1"
$LocalWebScript = Join-Path $PSScriptRoot "local-web.ps1"
$StateDir = Join-Path $RepoRoot ".local"
$StackStateFile = Join-Path $StateDir "ambrosia-stack.json"
$ApiLogFile = Join-Path $StateDir "ambrosia-api.log"
$ApiErrLogFile = Join-Path $StateDir "ambrosia-api.err.log"
$WebLogFile = Join-Path $StateDir "ambrosia-web.log"
$WebErrLogFile = Join-Path $StateDir "ambrosia-web.err.log"

function Ensure-StateDir {
  if (-not (Test-Path $StateDir)) {
    New-Item -ItemType Directory -Path $StateDir | Out-Null
  }
}

function Write-StackState([int]$ApiPid, [int]$WebPid) {
  Ensure-StateDir
  $payload = @{
    apiPid = $ApiPid
    webPid = $WebPid
    updatedAt = (Get-Date).ToString("s")
  } | ConvertTo-Json -Compress
  Set-Content -Path $StackStateFile -Value $payload -NoNewline
}

function Read-StackState {
  if (-not (Test-Path $StackStateFile)) {
    return $null
  }
  try {
    return (Get-Content -Path $StackStateFile -Raw | ConvertFrom-Json)
  } catch {
    return $null
  }
}

function Clear-StackState {
  if (Test-Path $StackStateFile) {
    Remove-Item -Path $StackStateFile -Force
  }
}

function Wait-ForUrl([string]$Url, [int]$TimeoutSeconds = 60) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -eq 200) {
        return $true
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

function Get-PidFromScriptOutput([string[]]$Lines) {
  foreach ($line in $Lines) {
    if ($line -match "^PID:\s+(\d+)$") {
      return [int]$matches[1]
    }
  }
  return 0
}

function Start-Stack {
  Ensure-StateDir

  try {
    $apiOutput = & powershell.exe -ExecutionPolicy Bypass -File $LocalApiScript start
    $apiOutput | ForEach-Object { Write-Output $_ }

    $webOutput = & powershell.exe -ExecutionPolicy Bypass -File $LocalWebScript start
    $webOutput | ForEach-Object { Write-Output $_ }

    Write-StackState (Get-PidFromScriptOutput $apiOutput) (Get-PidFromScriptOutput $webOutput)
    Write-Output "Ambrosia stack is up."
    Write-Output "Web: http://127.0.0.1:3000"
    Write-Output "API: http://127.0.0.1:8000"
  } catch {
    & powershell.exe -ExecutionPolicy Bypass -File $LocalWebScript stop | Out-Null
    & powershell.exe -ExecutionPolicy Bypass -File $LocalApiScript stop | Out-Null
    Clear-StackState
    throw
  }
}

function Stop-Stack {
  & powershell.exe -ExecutionPolicy Bypass -File $LocalWebScript stop | ForEach-Object { Write-Output $_ }
  & powershell.exe -ExecutionPolicy Bypass -File $LocalApiScript stop | ForEach-Object { Write-Output $_ }
  Clear-StackState
  Write-Output "Ambrosia stack is stopped."
}

function Restart-Stack {
  Stop-Stack
  Start-Sleep -Seconds 1
  Start-Stack
}

function Show-Status {
  $apiReady = Wait-ForUrl "http://127.0.0.1:8000/health" -TimeoutSeconds 3
  $webReady = Wait-ForUrl "http://127.0.0.1:3000" -TimeoutSeconds 3
  $state = Read-StackState

  if ($apiReady -or $webReady) {
    Write-Output "Ambrosia stack status:"
    Write-Output "API: $(if ($apiReady) { 'up' } else { 'down' })"
    Write-Output "Web: $(if ($webReady) { 'up' } else { 'down' })"
    if ($state) {
      if ($state.apiPid) {
        Write-Output "Recorded API PID: $($state.apiPid)"
      }
      if ($state.webPid) {
        Write-Output "Recorded Web PID: $($state.webPid)"
      }
    }
    return
  }

  Write-Output "Ambrosia stack is not running."
}

function Show-Logs {
  Ensure-StateDir
  $paths = @($ApiLogFile, $ApiErrLogFile, $WebLogFile, $WebErrLogFile)
  foreach ($path in $paths) {
    if (-not (Test-Path $path)) {
      New-Item -ItemType File -Path $path | Out-Null
    }
  }

  Write-Output "Streaming Ambrosia stack logs. Press Ctrl+C to stop."
  Get-Content -Path $paths -Wait
}

function Serve-Stack {
  Ensure-StateDir

  & powershell.exe -ExecutionPolicy Bypass -File $LocalApiScript start | ForEach-Object { Write-Output $_ }
  if (-not (Wait-ForUrl "http://127.0.0.1:8000/health" -TimeoutSeconds 30)) {
    throw "Ambrosia API did not become ready."
  }

  Write-Output "Serving Ambrosia stack."
  Write-Output "Web: http://127.0.0.1:3000"
  Write-Output "API: http://127.0.0.1:8000"
  Write-Output "Press Ctrl+C to stop."

  try {
    & powershell.exe -ExecutionPolicy Bypass -File $LocalWebScript serve
  } finally {
    & powershell.exe -ExecutionPolicy Bypass -File $LocalApiScript stop | Out-Null
  }
}

switch ($Command) {
  "serve" { Serve-Stack }
  "start" { Start-Stack }
  "stop" { Stop-Stack }
  "restart" { Restart-Stack }
  "status" { Show-Status }
  "logs" { Show-Logs }
  default { throw "Unknown command: $Command" }
}
