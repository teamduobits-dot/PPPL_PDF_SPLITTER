$ErrorActionPreference = "Stop"

Write-Host "=== PPPL PDF Splitter Run ===" -ForegroundColor Cyan

if (!(Test-Path ".\.venv")) {
    throw "Virtual environment not found. Please run .\setup.ps1 first."
}

& .\.venv\Scripts\Activate.ps1

python .\main.py