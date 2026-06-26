@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set QUIET=0
if /I "%~1"=="/quiet" set QUIET=1

echo ══════════════════════════════════════════
echo   سامانه تدارکات — نصب اولیه
echo ══════════════════════════════════════════
echo.

if not exist "share.config.json" (
  copy share.config.example.json share.config.json >nul
  echo ✓ share.config.json ساخته شد — مسیر share را تنظیم کنید.
  echo.
)

where py >nul 2>&1 && set PY=py -3 || set PY=python
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo ❌ Python یافت نشد — python.org را نصب کنید
  exit /b 1
)

if not exist ".venv" (
  echo ایجاد محیط مجازی Python ...
  %PY% -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
python -m pip install -r backend\requirements.txt -q
echo ✓ وابستگی‌های Python

python scripts\build_db_template.py

if not exist "frontend\vendor\tailwind.css" (
  if exist "scripts\download_vendor.bat" call scripts\download_vendor.bat
) else (
  echo ✓ فایل‌های vendor
)

echo %date% %time%> .installed
echo.
echo ✓ نصب کامل — اجرا: run.bat
echo   راه‌اندازی share: scripts\init_share.bat
echo.
if "%QUIET%"=="0" pause