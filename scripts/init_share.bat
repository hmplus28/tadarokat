@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo.
  echo [ERROR] Run install.bat first.
  echo.
  pause
  exit /b 1
)

echo.
echo Initializing share and users...
echo.

"%PY%" scripts\init_share.py %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo [ERROR] init_share failed - check share_users.seed.json in data folder.
) else (
  echo Press any key to close...
)
pause
exit /b %RC%