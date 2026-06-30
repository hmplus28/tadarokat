@echo off
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo.
  echo [ERROR] Not installed yet - run install.bat first.
  echo.
  pause
  exit /b 1
)

echo.
echo Starting server...  Press Ctrl+C to stop
echo (PowerShell users: prefer .\run.ps1 for better Unicode support)
echo.

"%PY%" scripts\launcher.py %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [ERROR] Server stopped (exit code %RC%)
  echo.
  pause
)
exit /b %RC%