@echo off
set "SCRIPT_DIR=%~dp0"
set "CLI_SHIM=%SCRIPT_DIR%ambrosia.cmd"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

if not exist "%CLI_SHIM%" (
  echo ERROR: Could not find "%CLI_SHIM%".
  goto :eof
)

if not exist "%REPO_ROOT%" (
  echo ERROR: Repo root path not found:
  echo   "%REPO_ROOT%"
  goto :eof
)

set "PATH=%SCRIPT_DIR%;%PATH%"
cd /d "%REPO_ROOT%" || (
  echo ERROR: Could not change directory to "%REPO_ROOT%".
  goto :eof
)

echo Ambrosia CLI window ready.
echo Current directory: %CD%
echo Use: ambrosia --help
echo Use: ambrosia commands list
