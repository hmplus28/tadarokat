@echo off
REM نصب سامانه تدارکات — پنجره همیشه باز می‌ماند تا خطا دیده شود
setlocal EnableExtensions
cd /d "%~dp0"

chcp 65001 >nul 2>&1

set "QUIET_ARG=%~1"
set "ERR=0"

REM ── یافتن Python ──
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
  echo [خطا] Python یافت نشد.
  echo.
  echo  1. از https://www.python.org/downloads/ نصب کنید
  echo  2. هنگام نصب تیک "Add python.exe to PATH" را بزنید
  echo  3. CMD را ببندید و دوباره install.bat را اجرا کنید
  echo.
  set ERR=1
  goto :DONE
)

echo Python:
%PY_LAUNCHER% --version
if errorlevel 1 (
  echo [خطا] اجرای Python ناموفق
  set ERR=1
  goto :DONE
)
echo.

REM ── نصب با اسکریپت پایتون (پیام خطای واضح) ──
%PY_LAUNCHER% scripts\install_windows.py %QUIET_ARG%
if errorlevel 1 set ERR=1

:DONE
echo.
if "%ERR%"=="1" (
  echo ══════════════════════════════════════════
  echo   نصب ناموفق — متن خطای بالا را بخوانید
  echo ══════════════════════════════════════════
) else (
  echo برای بستن این پنجره یک کلید بزنید...
)
pause
exit /b %ERR%