# Tadarokat PowerShell runner
# Recommended for PowerShell users. Better Unicode support.
# Usage: .\run.ps1

$ErrorActionPreference = "Continue"

# UTF-8 output (critical for Persian text)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host ""
    Write-Host "[ERROR] Not installed yet. Run .\install.ps1 (or install.bat) first." -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "Starting Tadarokat server...   Press Ctrl+C to stop" -ForegroundColor Cyan
Write-Host ""

& $python "scripts/launcher.py" $args
$rc = $LASTEXITCODE

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Server stopped with exit code $rc" -ForegroundColor Red
    Write-Host "Press Enter to close..."
    Read-Host | Out-Null
}

exit $rc
