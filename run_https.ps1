# Run with HTTPS (fixes "attribution reporting origins are trustworthy")
# Если Chrome блокирует: chrome://flags/#allow-insecure-localhost — включите и перезапустите браузер
# Альтернатива: .\run_http.ps1 — запуск по HTTP без SSL
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".dev\key.pem")) {
    python scripts/gen_ssl_cert.py
}
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --ssl-keyfile=.dev/key.pem --ssl-certfile=.dev/cert.pem
