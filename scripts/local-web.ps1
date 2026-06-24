param(
  [string]$Command = "start"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$WebRoot = Join-Path $RepoRoot "apps\web"
$StateDir = Join-Path $RepoRoot ".local"
$PidFile = Join-Path $StateDir "ambrosia-web.pid"
$LogFile = Join-Path $StateDir "ambrosia-web.log"
$ErrorLogFile = Join-Path $StateDir "ambrosia-web.err.log"
$Port = if ($env:PORT) { $env:PORT } else { "3000" }
$Url = "http://127.0.0.1:$Port"
$NextCli = Join-Path $WebRoot "node_modules\next\dist\bin\next"
$RunnerScript = Join-Path $PSScriptRoot "run-web-server.ps1"

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

function Get-PortPid {
  try {
    $match = netstat -ano -p tcp | Select-String -Pattern "LISTENING\s+(\d+)\s*$"
    $portPattern = "127\.0\.0\.1:$Port|0\.0\.0\.0:$Port|\[::\]:$Port"
    foreach ($line in $match) {
      $text = $line.ToString()
      if ($text -match $portPattern) {
        $parts = ($text -replace "\s+", " ").Trim().Split(" ")
        return [int]$parts[-1]
      }
    }
  } catch {
    return $null
  }
  return $null
}

function Wait-ForServer([int]$TimeoutSeconds = 60) {
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

function Ensure-Build {
  $buildId = Join-Path $WebRoot ".next\BUILD_ID"
  if (Test-Path $buildId) {
    return
  }

  & pnpm.cmd build:web
  if ($LASTEXITCODE -ne 0) {
    throw "Web build failed."
  }
}

function Start-Server {
  Ensure-StateDir

  if (Wait-ForServer -TimeoutSeconds 3) {
    Write-Output "Ambrosia web is already running at $Url"
    return
  }

  Ensure-Build

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
      "-WebRoot", $WebRoot,
      "-NextCli", $NextCli,
      "-Port", $Port,
      "-LogFile", $LogFile,
      "-ErrorLogFile", $ErrorLogFile
    ) `
    -WorkingDirectory $WebRoot `
    -WindowStyle Hidden `
    -PassThru

  Set-Content -Path $PidFile -Value $process.Id -NoNewline

  if (-not (Wait-ForServer -TimeoutSeconds 60)) {
    throw "Ambrosia web did not become ready on $Url. Check $LogFile"
  }

  $serverPid = Get-PortPid

  Write-Output "Ambrosia web is running at $Url"
  if ($serverPid) {
    Write-Output "PID: $serverPid"
  }
  Write-Output "Log: $LogFile"
}

function Serve-Server {
  Ensure-StateDir
  Ensure-Build

  Write-Output "Serving Ambrosia web at $Url"
  Write-Output "Press Ctrl+C to stop."

  & powershell.exe `
    -ExecutionPolicy Bypass `
    -File $RunnerScript `
    -WebRoot $WebRoot `
    -NextCli $NextCli `
    -Port $Port `
    -LogFile $LogFile `
    -ErrorLogFile $ErrorLogFile
}

function Stop-Server {
  $serverPid = Read-Pid
  $portPid = Get-PortPid
  if (-not $serverPid) {
    $serverPid = $portPid
  }

  if (-not $serverPid -or -not (Test-PidAlive $serverPid)) {
    Clear-Pid
    Write-Output "Ambrosia web is not running."
    return
  }

  Stop-Process -Id $serverPid -Force
  if ($portPid -and $portPid -ne $serverPid -and (Test-PidAlive $portPid)) {
    Stop-Process -Id $portPid -Force
  }
  Clear-Pid
  Write-Output "Ambrosia web stopped."
}

function Show-Status {
  $serverPid = Read-Pid
  $portPid = Get-PortPid
  if (-not $serverPid) {
    $serverPid = $portPid
  }
  $alive = $serverPid -and (Test-PidAlive $serverPid)
  $ready = Wait-ForServer -TimeoutSeconds 3

  if ($ready) {
    Write-Output "Ambrosia web is running at $Url"
    if ($portPid) {
      Write-Output "PID: $portPid"
    } elseif ($serverPid) {
      Write-Output "PID: $serverPid"
    }
    Write-Output "Log: $LogFile"
    return
  }

  if ($alive) {
    Write-Output "Ambrosia web process exists (PID $serverPid) but is not responding on $Url"
    Write-Output "Log: $LogFile"
    return
  }

  Write-Output "Ambrosia web is not running."
}

switch ($Command) {
  "serve" { Serve-Server }
  "start" { Start-Server }
  "stop" { Stop-Server }
  "restart" {
    Stop-Server
    Start-Sleep -Seconds 1
    Start-Server
  }
  "status" { Show-Status }
  default { throw "Unknown command: $Command" }
}
