# Start app on port 8080 (default uvicorn without --port uses 8000).
# Browser: http://127.0.0.1:8080/   If localhost fails, use 127.0.0.1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "  Typical infrastructure - port 8080" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8080/" -ForegroundColor Green
Write-Host ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
