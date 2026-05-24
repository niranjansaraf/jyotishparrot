# Jyotish — Vedic Astrology Agent launcher
Set-Location $PSScriptRoot

# Check .env exists
if (-not (Test-Path ".env")) {
    Write-Host "`n  No .env file found. Creating one..." -ForegroundColor Yellow
    @"
ANTHROPIC_API_KEY=your_key_here
"@ | Out-File -Encoding utf8 ".env"
    Write-Host "  Edit .env and add your ANTHROPIC_API_KEY, then re-run this script.`n" -ForegroundColor Yellow
    pause
    exit
}

# Check/create virtualenv
if (-not (Test-Path "venv")) {
    Write-Host "`n  Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
}

# Activate and install deps
& venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

Write-Host "`n  Starting Jyotish at http://localhost:5000`n" -ForegroundColor Green
python app.py
