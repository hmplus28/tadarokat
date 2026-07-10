@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title Tadarokat - Starting...

where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Docker is not installed or not in PATH.
    echo  Install Docker Desktop, then run this file again.
    echo  Guide: RAHNAMA_NASB.md
    echo.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Docker Desktop is not running.
    echo  Open Docker Desktop and wait until it shows "Running".
    echo  Guide: RAHNAMA_NASB.md
    echo.
    pause
    exit /b 1
)

echo.
echo  ==========================================
echo    Tadarokat - one-click start
echo  ==========================================
echo.
echo  Project folder: %CD%
echo  URL:  http://localhost:8000
echo  Login: admin / admin1234
echo.

docker compose up --build
set EXIT_CODE=%ERRORLEVEL%

echo.
if not "%EXIT_CODE%"=="0" (
    echo  Error starting the app. Exit code: %EXIT_CODE%
    echo  Read the messages above. Guide: RAHNAMA_NASB.md
) else (
    echo  Service stopped.
)
echo.
pause
exit /b %EXIT_CODE%