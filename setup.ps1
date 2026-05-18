param()

$ErrorActionPreference = "Stop"

Write-Host "=== PPPL PDF Splitter Setup ===" -ForegroundColor Cyan

if (!(Test-Path ".\.venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host "Installing requirements..." -ForegroundColor Yellow
pip install -r .\requirements.txt

Write-Host "✅ Setup complete!" -ForegroundColor Green