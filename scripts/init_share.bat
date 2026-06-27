@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
chcp 65001 >nul 2>&1

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo.
  echo [خطا] ابتدا install.bat را اجرا کنید.
  echo.
  pause
  exit /b 1
)

echo.
echo راه‌اندازی share و کاربران...
echo.

"%PY%" scripts\init_share.py %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
  echo [خطا] init_share ناموفق — فایل share_users.seed.json را در پوشه data بررسی کنید.
) else (
  echo برای بستن یک کلید بزنید...
)
pause >nul
exit /b %RC%