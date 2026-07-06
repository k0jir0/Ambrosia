@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

set "VENV_AMBROSIA=%REPO_ROOT%\.venv\Scripts\ambrosia.exe"
set "VENV_PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"

if exist "%VENV_AMBROSIA%" (
  "%VENV_AMBROSIA%" %*
  exit /b %ERRORLEVEL%
)

if exist "%VENV_PYTHON%" (
  "%VENV_PYTHON%" -m ambrosia_cli.main %*
  exit /b %ERRORLEVEL%
)

echo ERROR: Could not find .venv\Scripts\ambrosia.exe or .venv\Scripts\python.exe under "%REPO_ROOT%".
echo Create the venv first.
exit /b 1
