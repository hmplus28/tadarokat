# Tadarokat Windows PowerShell Installer
# Run with: .\install.ps1   (from project root in PowerShell)
# This provides better Unicode (Persian) support than .bat

$ErrorActionPreference = "Stop"

# Ensure UTF-8 in this session (fixes garbled Persian characters)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Tadarokat - Windows PowerShell install" -ForegroundColor Cyan
Write-Host "=========================================="

# Find Python (prefer py launcher, then python)
$pythonCmd = $null
$tryCmds = @("py -3", "python", "python3")

foreach ($c in $tryCmds) {
    $exe = $c.Split()[0]
    $arg = if ($c.Split().Count -gt 1) { $c.Split()[1] } else { $null }
    try {
        if ($arg) {
            & $exe $arg --version | Out-Null
        } else {
            & $exe --version | Out-Null
        }
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $c
            Write-Host "Found Python: $pythonCmd"
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "[ERROR] Python not found." -ForegroundColor Red
    Write-Host "1. Install from https://www.python.org/downloads/"
    Write-Host "2. IMPORTANT: Check 'Add python.exe to PATH' during install"
    Write-Host "3. Close and reopen PowerShell, then run .\install.ps1 again"
    exit 1
}

# Run the Windows install script
try {
    $parts = $pythonCmd.Split()
    & $parts[0] $parts[1..99] "scripts/install_windows.py" --quiet
    if ($LASTEXITCODE -ne 0) { throw "Install script failed" }
} catch {
    Write-Host "[ERROR] Installation failed. See messages above." -ForegroundColor Red
    exit 1
}

# Ensure bcrypt pinned after install (in case)
Write-Host "Ensuring bcrypt==4.0.1 for compatibility..."

# --- FIX: Silence pip's stderr deprecation warnings (e.g. vboxapi egg) ---
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
& $parts[0] $parts[1..99] -m pip install "bcrypt==4.0.1" --quiet 2>&1 | Out-Null
$ErrorActionPreference = $prevEAP
# --- END FIX ---

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  INSTALL COMPLETE" -ForegroundColor Green
Write-Host "=========================================="
Write-Host "  Run:            .\run.ps1  (or run.bat)"
Write-Host "  Users (baked in):"
Write-Host "    admin/admin123, mostafa/mostafa123, fabri/fabri123,"
Write-Host "    behnaz/behnaz123, manager/manager123, anbar/anbar123"
Write-Host "  Root Excel imported & cached during install."
Write-Host "  Set primary_data_dir in UI (System Panel) to move DB+Excel."
Write-Host "  Browser:        http://127.0.0.1:8000"
Write-Host ""
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")