@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>&1

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo.
  echo [خطا] نصب انجام نشده — ابتدا install.bat را اجرا کنید.
  echo.
  pause
  exit /b 1
)

echo.
echo در حال اجرای سامانه...  Ctrl+C برای توقف
echo.

"%PY%" scripts\launcher.py %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [خطا] سرور متوقف شد (کد %RC%)
  echo.
  pause
)
exit /b %RC%