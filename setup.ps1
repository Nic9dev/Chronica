# Chronica Setup Script (Windows PowerShell)
# Automates: venv -> pip install -> Claude Desktop config

$ErrorActionPreference = "Stop"

Write-Host "=== Chronica Setup ===" -ForegroundColor Green

# Verify project root
if (-not (Test-Path "requirements.txt") -or -not (Test-Path "run_server.py")) {
    Write-Host "Error: Run this script from project root (Chronica/)" -ForegroundColor Red
    Write-Host "  cd path\to\Chronica" -ForegroundColor Yellow
    exit 1
}

# 1. Create venv
if (-not (Test-Path ".venv")) {
    Write-Host ""
    Write-Host "[1/3] Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: venv creation failed. Ensure Python 3.10+ is installed." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Done" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[1/3] Virtual environment exists (skip)" -ForegroundColor Cyan
}

# 2. Install dependencies
Write-Host ""
Write-Host "[2/3] Installing dependencies..." -ForegroundColor Cyan
& .\.venv\Scripts\pip.exe install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: pip install failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Done" -ForegroundColor Green

# 3. Add Chronica to Claude Desktop config
Write-Host ""
Write-Host "[3/3] Registering Chronica in Claude Desktop..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe scripts\setup_config.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Config update failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "Restart Claude Desktop and start a new conversation." -ForegroundColor Yellow
