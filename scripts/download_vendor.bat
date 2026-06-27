@echo off
setlocal
cd /d "%~dp0\.."
set VENDOR=frontend\vendor
set FONTS=%VENDOR%\fonts\vazir
if not exist "%VENDOR%" mkdir "%VENDOR%"
if not exist "%FONTS%" mkdir "%FONTS%"

powershell -NoProfile -Command ^
  "$v='%VENDOR%'; $f='%FONTS%';" ^
  "Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js' -OutFile \"$v\chart.umd.min.js\";" ^
  "Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js' -OutFile \"$v\xlsx.full.min.js\";" ^
  "Invoke-WebRequest -Uri 'https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.css' -OutFile \"$v\jalalidatepicker.min.css\";" ^
  "Invoke-WebRequest -Uri 'https://unpkg.com/@majidh1/jalalidatepicker/dist/jalalidatepicker.min.js' -OutFile \"$v\jalalidatepicker.min.js\";" ^
  "Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-Regular.woff2' -OutFile \"$f\Vazir-Regular.woff2\";" ^
  "Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-Bold.woff2' -OutFile \"$f\Vazir-Bold.woff2\";"

echo [OK] vendor assets downloaded