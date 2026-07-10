@echo off
cd /d "%~dp0"
chcp 65001 >nul
title تدارکات — در حال بالا آوردن...

where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Docker نصب نیست. راهنما: RAHNAMA_NASB.md
    echo.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Docker Desktop روشن نیست.
    echo  برنامه Docker Desktop را باز کنید و صبر کنید تا Ready شود.
    echo  راهنما: RAHNAMA_NASB.md
    echo.
    pause
    exit /b 1
)

echo.
echo  ==========================================
echo    تدارکات — فقط همین یک دستور کافی است
echo  ==========================================
echo.
echo  پوشه پروژه: %CD%
echo  آدرس: http://localhost:8000
echo  ورود: admin / admin1234
echo.

docker compose up --build
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% neq 0 (
    echo  خطا در اجرا ^(کد %EXIT_CODE%^). پیام بالا را بخوانید.
    echo  راهنما: RAHNAMA_NASB.md
) else (
    echo  سرویس متوقف شد.
)
echo.
pause
exit /b %EXIT_CODE%