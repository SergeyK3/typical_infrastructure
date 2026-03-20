# Добавить правило брандмауэра для Python (запуск от имени администратора)
# ПКМ по PowerShell -> "Запуск от имени администратора", затем: .\scripts\add_firewall_rule.ps1

$pythonPath = (Get-Command python).Source
if (-not $pythonPath) {
    Write-Host "Python не найден в PATH" -ForegroundColor Red
    exit 1
}

$ruleName = "Python - Local Development Server"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Правило '$ruleName' уже существует." -ForegroundColor Yellow
    exit 0
}

New-NetFirewallRule -DisplayName $ruleName `
    -Direction Inbound `
    -Program $pythonPath `
    -Action Allow `
    -Profile Private, Domain

Write-Host "Правило добавлено. Перезапустите сервер и попробуйте снова." -ForegroundColor Green
