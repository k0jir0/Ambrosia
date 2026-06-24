param(
  [string]$ApiRoot,
  [string]$Port,
  [string]$LogFile,
  [string]$ErrorLogFile
)

$ErrorActionPreference = "Continue"

$PythonExe = Join-Path $ApiRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
  throw "Ambrosia API virtual environment not found at $PythonExe. Run 'uv sync' in services/api first."
}

Set-Location $ApiRoot

if (-not (Test-Path (Split-Path -Parent $LogFile))) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $LogFile) | Out-Null
}

& $PythonExe -m uvicorn app.main:app --host 0.0.0.0 --port $Port 1>> $LogFile 2>> $ErrorLogFile
