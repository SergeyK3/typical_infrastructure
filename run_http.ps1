# Run with HTTP (no SSL) — для локальной разработки без проблем с сертификатами
# Если Chrome не открывает: 1) перезапустите сервер  2) попробуйте .\run_http_8080.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Stopping Docker Compose app if running (manual dev workflow)..." -ForegroundColor DarkYellow
if (Get-Command docker -ErrorAction SilentlyContinue) {
  $composeFile = Join-Path $root "docker-compose.yml"
  if (Test-Path $composeFile) {
    $dockerIds = @(docker compose -f $composeFile ps -q app 2>$null)
    if ($dockerIds.Count) {
      docker compose -f $composeFile stop app 2>$null | Out-Null
      Write-Host "  Docker app stopped." -ForegroundColor Green
    }
  }
}

Write-Host "Stopping stale uvicorn app.main processes (any Python)..." -ForegroundColor DarkYellow
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' } |
  ForEach-Object {
    Write-Host "  kill PID $($_.ProcessId): $($_.CommandLine.Substring(0, [Math]::Min(100, $_.CommandLine.Length)))"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
Start-Sleep -Seconds 1

Write-Host "Stopping any process still listening on port 8100..." -ForegroundColor DarkYellow
for ($attempt = 1; $attempt -le 4; $attempt++) {
  $listeners = @(Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue)
  if (-not $listeners.Count) { break }
  $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $pids) {
    try {
      # Uvicorn --reload: parent reloader + child worker; kill the whole tree.
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
      Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch {}
  }
  Start-Sleep -Seconds 1
}
$left = @(Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue)
if ($left.Count) {
  Write-Host "WARNING: port 8100 still in use by PID(s): $($left.OwningProcess -join ', ')" -ForegroundColor Red
  Write-Host "Run: Get-NetTCPConnection -LocalPort 8100 | Select OwningProcess; Stop-Process -Id <pid> -Force" -ForegroundColor Red
} else {
  Write-Host "Port 8100 is free." -ForegroundColor Green
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtualenv not found: $python. Create it: python -m venv .venv; then .\.venv\Scripts\pip install -r requirements.txt"
}
& $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
