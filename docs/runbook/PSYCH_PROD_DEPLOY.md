# Runbook: Psychological Testing — prod deploy + smoke

Версия: 0.1  
Дата: 2026-05-22  
Статус: Phase 4a (UNC + SA + RBAC env)

---

## Назначение

Пошаговый чеклист для **production** psychological testing: Google Drive (UNC + service account), persist DB, RBAC env-флаги, smoke после деплоя.

Связанные документы:

- [17_GDRIVE_STORAGE.md](../hr-os/psychological_testing/17_GDRIVE_STORAGE.md) — Drive API, формат `pdf_ref`
- [00_NEXT_STEPS.md](../hr-os/psychological_testing/00_NEXT_STEPS.md) — roadmap Phase 4a
- [PRODUCTION_LIKE_DEPLOYMENT.md](PRODUCTION_LIKE_DEPLOYMENT.md) — общий Docker/env runbook

---

## 1. Pre-flight (до деплоя кода)

1. Убедиться, что на prod развёрнут коммит **≥ 67df8de** (manager RBAC + Drive + persist_db).
2. На prod-сервере есть `app.db` с хотя бы одной завершённой psych-сессией (Telegram E2E или импорт).
3. В HR есть account с ролью `hr_admin` / `admin` / `platform_admin` для пилотного клиента.

---

## 2. Google Cloud + Drive

1. **Service account** в GCP → скачать JSON ключ.
2. **Shared Drive / папка** → Share → email SA (`...@....iam.gserviceaccount.com`) → **Editor** (или Content manager на Shared Drive).
3. Скопировать **Folder ID** из URL папки → `PSYCH_TESTING_GDRIVE_FOLDER_ID`.

---

## 3. Секреты на Windows prod (UNC)

JSON ключ **не кладём** в каталог приложения. Типичный путь:

```env
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=\\fileserver\hr-secrets\psych-testing-sa.json
```

### Права на UNC

Учётная запись, под которой работает **uvicorn / IIS / Windows Service**, должна иметь **Read** на файл JSON:

```powershell
# Проверка от имени службы (замените DOMAIN\svc-typical-infra)
Test-Path "\\fileserver\hr-secrets\psych-testing-sa.json"
Get-Acl "\\fileserver\hr-secrets\psych-testing-sa.json" | Format-List
```

Альтернатива без UNC — inline JSON в env (Docker/K8s):

```env
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_INLINE={"type":"service_account",...}
```

---

## 4. Переменные `.env` на prod

Минимальный набор для Phase 4a:

```env
# Persistence
PSYCH_TESTING_PERSIST_JSON=1
PSYCH_TESTING_PERSIST_DB=1

# RBAC pilot (все три = 1 на prod)
PSYCH_TESTING_RBAC_ASSIGN=1
PSYCH_TESTING_RBAC_VIEW=1
PSYCH_TESTING_RBAC_EXPORT=1

# Google Drive
PSYCH_TESTING_GDRIVE=1
PSYCH_TESTING_GDRIVE_FOLDER_ID=<folder_id>
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=\\fileserver\hr-secrets\psych-testing-sa.json
PSYCH_TESTING_GDRIVE_UPLOAD_MANIFEST=1
PSYCH_TESTING_PDF_CACHE=hash

# Telegram (если worker в uvicorn)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ENABLE_POLLING=1
TELEGRAM_POLLING_RUN_IN_UVICORN=1
PSYCH_TESTING_ENABLE_POLLING=1
PSYCH_TESTING_TELEGRAM_OUTBOUND=http

# Напоминания о дедлайне
PSYCH_TESTING_REMINDERS=1
PSYCH_TESTING_REMINDER_HOURS_BEFORE=24
PSYCH_TESTING_REMINDER_POLL_SEC=300
```

Полный шаблон — корневой `.env.example` (секция Psychological testing).

---

## 5. Деплой

```powershell
cd "D:\path\to\10 Typical_infrastructure"
git pull origin main
# обновить .env на prod (см. §4)
.\run_http.ps1
# или Windows Service / IIS reverse proxy → uvicorn app.main:app --host 0.0.0.0 --port 8100
```

После рестарта:

```powershell
curl http://127.0.0.1:8100/health/ready
curl http://127.0.0.1:8100/api/psychological-testing/status
```

Ожидаемый `/status`:

| Поле | Prod |
|------|------|
| `persist_db_enabled` | `true` |
| `gdrive_configured` | `true` |
| `rbac_*_enforced` | все `true` |
| `storage_label` | Google Drive (настроено) |

---

## 6. Smoke на prod-сервере (полный)

**На машине приложения** (доступ к `.env` + `app.db` + UNC):

```powershell
cd "D:\path\to\10 Typical_infrastructure"
python scripts/verify_psych_gdrive.py --probe
python scripts/smoke_psych_pilot.py
```

Или одной командой:

```powershell
.\scripts\probe_psych_prod.ps1
```

`smoke_psych_pilot.py` без аргументов:

- читает `.env` и `app.db`;
- находит org с завершёнными сессиями;
- проверяет RBAC 403/200;
- делает export PDF → `pdf_ref` начинается с `gdrive:`.

---

## 7. Smoke с рабочей станции (удалённо)

Без доступа к `app.db` — только HTTP-проверки конфигурации:

```bash
python scripts/smoke_psych_pilot.py --url https://prod.example.com --status-only
```

С полным export (нужны ID из Workspace или SQL):

```bash
python scripts/smoke_psych_pilot.py --url https://prod.example.com \
  --client-id <uuid> \
  --account-id <uuid> \
  --employee-id <uuid>
```

ID можно взять:

- Workspace → psych UI → `/rbac-context?client_id=...` → `hr_admin_account_id`;
- employee_id — из списка сессий в UI или `GET /api/psychological-testing/sessions?client_id=...&account_id=...`.

---

## 8. Ручная проверка в Workspace

1. Открыть `/static/workspace/index.html` (или skill-assessment workspace).
2. Блок psych → **Статус**: persist_db, Drive, RBAC = включено.
3. Список сессий загружается (с `account_id` из rbac-context).
4. Export PDF → в ответе `pdf_ref: gdrive:...`, файл в Drive `{date}/{client_name}/`.
5. Ссылка «Открыть в Google Drive» в модалке сессии.

---

## 9. Troubleshooting

| Симптом | Причина | Действие |
|---------|---------|----------|
| `gdrive_configured: false` | нет SA path или folder id | проверить `.env`, `verify_psych_gdrive.py` |
| `ERROR: service account file not found` | UNC недоступен службе | ACL на шару, запуск smoke под той же учёткой |
| Drive probe 403/404 | папка не расшарена на SA | Share → email SA → Editor |
| export OK, `pdf_ref` локальный | `PSYCH_TESTING_GDRIVE=0` или upload failed | логи uvicorn, warning `psych_testing: uploaded to Drive` |
| sessions 403 с account_id | RBAC / неверный account | `/rbac-context`, роль hr_admin |
| smoke: no completed sessions | нет данных в `pt_test_sessions` | прогнать Telegram тест на prod |

---

## 10. Exit criteria Phase 4a

```text
☑ verify_psych_gdrive.py --probe на prod
☑ smoke_psych_pilot.py на prod (gdrive pdf_ref)
☑ RBAC env = 1, status endpoint подтверждает
☑ UNC: служба читает SA JSON
☑ PDF виден в Shared Drive после HR export
```

После закрытия — отметить в [00_NEXT_STEPS.md](../hr-os/psychological_testing/00_NEXT_STEPS.md) и перейти к **Workspace login + manager UI**.
