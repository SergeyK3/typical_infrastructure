# Start app on port 8080 (when 8100 is taken by another project).
# Browser: http://127.0.0.1:8080/   If localhost fails, use 127.0.0.1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "  Typical infrastructure - port 8080" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8080/" -ForegroundColor Green
Write-Host ""

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Virtualenv not found: $python"
}
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
