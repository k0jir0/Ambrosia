@echo off
setlocal

REM Launch Ambrosia CLI command menu from a stable relative location.
set "SCRIPT_DIR=%~dp0"
set "CLI_DIR=%SCRIPT_DIR%packages\cli"
set "SDK_DIR=%SCRIPT_DIR%packages\sdk-python"

if not exist "%CLI_DIR%" (
  echo [ERROR] Could not find CLI directory: "%CLI_DIR%"
  pause
  exit /b 1
)

if not exist "%SDK_DIR%" (
  echo [ERROR] Could not find SDK directory: "%SDK_DIR%"
  pause
  exit /b 1
)

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 'uv' is not installed or not on PATH.
  echo Install it from: https://docs.astral.sh/uv/
  pause
  exit /b 1
)

pushd "%CLI_DIR%"
if errorlevel 1 (
  echo [ERROR] Failed to enter CLI directory.
  pause
  exit /b 1
)

echo [INFO] Ensuring local CLI environment is installed...
uv sync
if errorlevel 1 (
  echo [ERROR] Failed to install Ambrosia CLI environment.
  popd
  pause
  exit /b 1
)

echo [INFO] Ambrosia CLI is ready.

:menu
echo.
echo ============================================================
echo                Ambrosia CLI Main Function Menu
echo ============================================================
uv run ambrosia commands list
if errorlevel 1 (
  echo [WARN] Could not load command list. You can still run custom commands.
)
echo.
echo [1] Show details for one command number
echo [2] Run an Ambrosia command
echo [3] Refresh menu
echo [Q] Quit
set "MENU_CHOICE="
set /p MENU_CHOICE=Select an option:

if /I "%MENU_CHOICE%"=="1" goto show_command
if /I "%MENU_CHOICE%"=="2" goto run_command
if /I "%MENU_CHOICE%"=="3" goto menu
if /I "%MENU_CHOICE%"=="Q" goto done

echo [WARN] Unknown option: "%MENU_CHOICE%"
goto menu

:show_command
set "COMMAND_INDEX="
set /p COMMAND_INDEX=Enter command number:
if "%COMMAND_INDEX%"=="" goto menu
uv run ambrosia commands show %COMMAND_INDEX%
echo.
pause
goto menu

:run_command
set "AMBROSIA_ARGS="
echo Example: health --detailed
set /p AMBROSIA_ARGS=Enter arguments after 'ambrosia':
if "%AMBROSIA_ARGS%"=="" goto menu
uv run ambrosia %AMBROSIA_ARGS%
echo.
pause
goto menu

:done
popd
echo [INFO] Exiting Ambrosia CLI launcher.
exit /b 0
