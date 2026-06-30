@echo off
REM Tadarokat installer - window stays open on success or error
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
setlocal EnableExtensions
cd /d "%~dp0"

set "QUIET_ARG=%~1"
set "ERR=0"

REM -- Find Python --
set "PY_LAUNCHER="
where py >nul 2>&1 && (
  py -3 --version >nul 2>&1 && set "PY_LAUNCHER=py -3"
)
if not defined PY_LAUNCHER (
  where python >nul 2>&1 && (
    python --version >nul 2>&1 && set "PY_LAUNCHER=python"
  )
)
if not defined PY_LAUNCHER (
  where python3 >nul 2>&1 && (
    python3 --version >nul 2>&1 && set "PY_LAUNCHER=python3"
  )
)

if not defined PY_LAUNCHER (
  echo.
  echo [ERROR] Python not found.
  echo.
  echo  1. Install from https://www.python.org/downloads/
  echo  2. Check "Add python.exe to PATH" during setup
  echo  3. Close CMD, then run install.bat again
  echo.
  set ERR=1
  goto :DONE
)

echo Python:
%PY_LAUNCHER% --version
if errorlevel 1 (
  echo [ERROR] Failed to run Python
  set ERR=1
  goto :DONE
)
echo.

REM -- Run installer script --
%PY_LAUNCHER% scripts\install_windows.py %QUIET_ARG%
if errorlevel 1 set ERR=1

:DONE
echo.
if "%ERR%"=="1" (
  echo ==========================================
  echo   INSTALL FAILED - read errors above
  echo ==========================================
) else (
  echo Press any key to close...
)
pause
exit /b %ERR%