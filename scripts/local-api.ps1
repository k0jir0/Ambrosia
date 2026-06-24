param(
  [string]$Command = "start"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApiRoot = Join-Path $RepoRoot "services\api"
$StateDir = Join-Path $RepoRoot ".local"
$PidFile = Join-Path $StateDir "ambrosia-api.pid"
$LogFile = Join-Path $StateDir "ambrosia-api.log"
$ErrorLogFile = Join-Path $StateDir "ambrosia-api.err.log"
$Port = if ($env:AMBROSIA_API_PORT) { $env:AMBROSIA_API_PORT } else { "8000" }
$Url = "http://127.0.0.1:$Port/health"
$RunnerScript = Join-Path $PSScriptRoot "run-api-server.ps1"

function Ensure-StateDir {
  if (-not (Test-Path $StateDir)) {
    New-Item -ItemType Directory -Path $StateDir | Out-Null
  }
}

function Read-Pid {
  if (-not (Test-Path $PidFile)) {
    return $null
  }
  $raw = (Get-Content -Path $PidFile -Raw).Trim()
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $null
  }
  return [int]$raw
}

function Clear-Pid {
  if (Test-Path $PidFile) {
    Remove-Item -Path $PidFile -Force
  }
}

function Test-PidAlive([int]$ProcessId) {
  if (-not $ProcessId) {
    return $false
  }
  try {
    Get-Process -Id $ProcessId | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Wait-ForApi([int]$TimeoutSeconds = 60) {
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

function Ensure-ApiEnv {
  $pythonExe = Join-Path $ApiRoot ".venv\Scripts\python.exe"
  if (Test-Path $pythonExe) {
    return
  }

  Push-Location $ApiRoot
  try {
    & uv sync
    if ($LASTEXITCODE -ne 0) {
      throw "uv sync failed."
    }
  } finally {
    Pop-Location
  }
}

function Start-Api {
  Ensure-StateDir

  if (Wait-ForApi -TimeoutSeconds 3) {
    Write-Output "Ambrosia API is already running at $Url"
    return
  }

  Ensure-ApiEnv

  if (Test-Path $LogFile) {
    Remove-Item -Path $LogFile -Force
  }
  if (Test-Path $ErrorLogFile) {
    Remove-Item -Path $ErrorLogFile -Force
  }

  $process = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @(
      "-ExecutionPolicy", "Bypass",
      "-File", $RunnerScript,
      "-ApiRoot", $ApiRoot,
      "-Port", $Port,
      "-LogFile", $LogFile,
      "-ErrorLogFile", $ErrorLogFile
    ) `
    -WorkingDirectory $ApiRoot `
    -WindowStyle Hidden `
    -PassThru

  Set-Content -Path $PidFile -Value $process.Id -NoNewline

  if (-not (Wait-ForApi -TimeoutSeconds 60)) {
    throw "Ambrosia API did not become ready on $Url. Check $LogFile"
  }

  Write-Output "Ambrosia API is running at http://127.0.0.1:$Port"
  Write-Output "PID: $($process.Id)"
  Write-Output "Log: $LogFile"
}

function Serve-Api {
  Ensure-StateDir
  Ensure-ApiEnv

  Write-Output "Serving Ambrosia API at http://127.0.0.1:$Port"
  Write-Output "Press Ctrl+C to stop."

  & powershell.exe `
    -ExecutionPolicy Bypass `
    -File $RunnerScript `
    -ApiRoot $ApiRoot `
    -Port $Port `
    -LogFile $LogFile `
    -ErrorLogFile $ErrorLogFile
}

function Stop-Api {
  $processId = Read-Pid

  if (-not $processId -or -not (Test-PidAlive $processId)) {
    Clear-Pid
    Write-Output "Ambrosia API is not running."
    return
  }

  Stop-Process -Id $processId -Force
  Clear-Pid
  Write-Output "Ambrosia API stopped."
}

function Show-Status {
  $processId = Read-Pid
  $alive = $processId -and (Test-PidAlive $processId)
  $ready = Wait-ForApi -TimeoutSeconds 3

  if ($ready) {
    Write-Output "Ambrosia API is running at http://127.0.0.1:$Port"
    if ($processId) {
      Write-Output "PID: $processId"
    }
    Write-Output "Log: $LogFile"
    return
  }

  if ($alive) {
    Write-Output "Ambrosia API process exists (PID $processId) but is not responding on $Url"
    Write-Output "Log: $LogFile"
    return
  }

  Write-Output "Ambrosia API is not running."
}

switch ($Command) {
  "serve" { Serve-Api }
  "start" { Start-Api }
  "stop" { Stop-Api }
  "restart" {
    Stop-Api
    Start-Sleep -Seconds 1
    Start-Api
  }
  "status" { Show-Status }
  default { throw "Unknown command: $Command" }
}
