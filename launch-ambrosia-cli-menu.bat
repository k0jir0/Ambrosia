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
uv run ambrosia status
if errorlevel 1 (
  echo [WARN] Could not read CLI/API status.
)
echo.
uv run ambrosia commands list
if errorlevel 1 (
  echo [WARN] Could not load command list. You can still run custom commands.
)
echo.
echo [1] Show current CLI/API status
echo [2] Choose API target for this launcher session
echo [3] Show details for one command number
echo [4] Run an Ambrosia command
echo [5] Run common quick checks
echo [6] Refresh menu
echo [Q] Quit
set "MENU_CHOICE="
set /p MENU_CHOICE=Select an option:

if /I "%MENU_CHOICE%"=="1" goto show_status
if /I "%MENU_CHOICE%"=="2" goto choose_target
if /I "%MENU_CHOICE%"=="3" goto show_command
if /I "%MENU_CHOICE%"=="4" goto run_command
if /I "%MENU_CHOICE%"=="5" goto quick_checks
if /I "%MENU_CHOICE%"=="6" goto menu
if /I "%MENU_CHOICE%"=="Q" goto done

echo [WARN] Unknown option: "%MENU_CHOICE%"
goto menu

:show_status
uv run ambrosia status
echo.
pause
goto menu

:choose_target
echo.
echo [L] Local API       http://127.0.0.1:8001
echo [S] Staging API     https://ambrosia-api-staging.onrender.com
echo [P] Production API  https://ambrosia-api-69t6.onrender.com
echo [C] Custom URL
set "TARGET_CHOICE="
set /p TARGET_CHOICE=Choose target:
if /I "%TARGET_CHOICE%"=="L" set "AMBROSIA_API_URL=http://127.0.0.1:8001"
if /I "%TARGET_CHOICE%"=="S" set "AMBROSIA_API_URL=https://ambrosia-api-staging.onrender.com"
if /I "%TARGET_CHOICE%"=="P" set "AMBROSIA_API_URL=https://ambrosia-api-69t6.onrender.com"
if /I "%TARGET_CHOICE%"=="C" goto custom_target
if "%AMBROSIA_API_URL%"=="" (
  echo [WARN] No target selected.
  pause
  goto menu
)
echo [INFO] Active launcher target: %AMBROSIA_API_URL%
set "PERSIST_TARGET="
set /p PERSIST_TARGET=Persist this target to the default Ambrosia profile? [y/N]:
if /I "%PERSIST_TARGET%"=="Y" uv run ambrosia quickstart --target custom --api-url %AMBROSIA_API_URL% --write-profile
pause
goto menu

:custom_target
set "CUSTOM_API_URL="
set /p CUSTOM_API_URL=Enter Ambrosia API URL:
if "%CUSTOM_API_URL%"=="" goto menu
set "AMBROSIA_API_URL=%CUSTOM_API_URL%"
echo [INFO] Active launcher target: %AMBROSIA_API_URL%
set "PERSIST_TARGET="
set /p PERSIST_TARGET=Persist this target to the default Ambrosia profile? [y/N]:
if /I "%PERSIST_TARGET%"=="Y" uv run ambrosia quickstart --target custom --api-url %AMBROSIA_API_URL% --write-profile
pause
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

:quick_checks
echo [INFO] Running status check...
uv run ambrosia status
echo.
echo [INFO] Running detailed health check...
uv run ambrosia health --detailed
echo.
echo [INFO] Running hosted market snapshot smoke check for GOOG...
uv run ambrosia market snapshot GOOG
echo.
pause
goto menu

:done
popd
echo [INFO] Exiting Ambrosia CLI launcher.
exit /b 0
