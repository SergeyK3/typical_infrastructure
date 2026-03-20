# Run with HTTP (no SSL) — для локальной разработки без проблем с сертификатами
# Если Chrome не открывает: 1) перезапустите сервер  2) попробуйте .\run_http_8080.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
