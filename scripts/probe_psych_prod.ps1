# On-server prod probe: Drive config + full psych pilot smoke.
# Run from repo root on the machine that hosts .env, app.db, and UNC access to SA JSON.
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "=== psych prod probe ===" -ForegroundColor Cyan
Write-Host "Repo:   $repoRoot"
Write-Host "Python: $python"
Write-Host ""

Write-Host "[1/2] verify_psych_gdrive.py --probe" -ForegroundColor Yellow
& $python scripts/verify_psych_gdrive.py --probe
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[2/2] smoke_psych_pilot.py (local .env + app.db)" -ForegroundColor Yellow
& $python scripts/smoke_psych_pilot.py
exit $LASTEXITCODE
