Param(
  [int]$Port = 8100
)

$ErrorActionPreference = "Stop"

Write-Host "Bootstrap: venv + deps + run" -ForegroundColor Cyan

if (!(Test-Path ".\.venv")) {
  Write-Host "Creating .venv..." -ForegroundColor Cyan
  python -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
$pip = ".\.venv\Scripts\pip.exe"

Write-Host "Installing requirements..." -ForegroundColor Cyan
& $pip install -r requirements.txt

Write-Host "Starting API on http://127.0.0.1:$Port" -ForegroundColor Green
& $python -m uvicorn app.main:app --reload --port $Port

