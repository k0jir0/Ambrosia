@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SHELL_INIT=%SCRIPT_DIR%cli-shell-init.bat"

if not exist "%SHELL_INIT%" (
  echo ERROR: Could not find "%SHELL_INIT%".
  exit /b 1
)

start "Ambrosia CLI" cmd /k ""%SHELL_INIT%""

exit /b 0
