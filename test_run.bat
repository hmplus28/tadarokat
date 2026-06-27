@echo off
REM One-click TEST: install + DB + users + Excel import + verify + run server
setlocal EnableExtensions
cd /d "%~dp0"

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
  echo.
  echo [ERROR] Python not found. Install from https://www.python.org/downloads/
  echo         Check "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)

echo.
echo ==========================================
echo   Tadarokat - ONE-CLICK TEST
echo ==========================================
echo.


%PY_LAUNCHER% scripts\test_setup.py --fresh --no-server
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [ERROR] Test setup failed (exit %RC%)
  echo.
  pause
  exit /b %RC%
)

echo.
echo Opening browser...
start "" http://127.0.0.1:8000/

echo.
echo Starting server (close window or Ctrl+C to stop)...
echo.
call run.bat
exit /b %ERRORLEVEL%
