# 17 — Google Drive storage (Phase F)

Версия: 0.1  
Дата: 2026-05-20  
Статус: **Реализовано** (service account, env on/off)

---

## 1. Контекст

До Phase F все артефакты только локально:

| Артефакт | Путь |
|----------|------|
| Session JSON | `data/sessions/v1/` (`PSYCH_TESTING_PERSIST_JSON=1`) |
| Manifest + PDF cache | `data/report_exports/` |
| `report.pdf_ref` | всегда `null` |

Legacy `07 PsychTest` использовал OAuth (`oauth_google_drive.py`) — **не переносится** (D18 в [11_TECHNICAL_DEBT.md](11_TECHNICAL_DEBT.md)). Target: **service account** + папка Drive, расшаренная на email SA.

---

## 2. Переменные окружения

| Env | Default | Назначение |
|-----|---------|------------|
| `PSYCH_TESTING_GDRIVE` | `0` | Master switch |
| `PSYCH_TESTING_GDRIVE_FOLDER_ID` | — | ID корневой папки (shared with SA) |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` | — | Путь к JSON ключу |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_INLINE` | — | Inline JSON (Docker) |
| `PSYCH_TESTING_GDRIVE_UPLOAD_MANIFEST` | `1` | Upload manifest при export |
| `PSYCH_TESTING_GDRIVE_UPLOAD_SESSIONS` | `0` | Upload session JSON при `DONE` |

Локальный кэш PDF (`PSYCH_TESTING_PDF_CACHE`) работает **параллельно**; при включённом Drive `pdf_ref` в ответе API — **`gdrive:{file_id}`**.

---

## 3. Формат `pdf_ref`

```
gdrive:1AbCdEfGhIjKlMnOpQrStUvWxYz
```

Также принимается полный URL: `https://drive.google.com/file/d/{id}/view`.

Скачивание через API: `GET /api/psychological-testing/export-pdf/file?pdf_ref=gdrive:...`

В session JSON после HR export: `report.pdf_ref` = тот же ref (все `session_refs` из manifest).

Опционально при upload session: `report.session_json_drive_ref`.

---

## 4. Код

| Модуль | Роль |
|--------|------|
| `integration/google_drive_client.py` | Drive API v3, SA auth |
| `integration/report_storage.py` | Env, upload/download, sync sessions |
| `integration/pdf_export_api.py` | Hook после generate PDF |
| `integration/session_persistence.py` | Hook после persist session |

---

## 5. Настройка Google Cloud

1. Создать service account + JSON key.
2. Создать папку в Drive, **Share** → email SA → Editor.
3. Скопировать Folder ID из URL в `PSYCH_TESTING_GDRIVE_FOLDER_ID`.
4. В `.env`: `PSYCH_TESTING_GDRIVE=1` + путь к ключу.

Зависимости: `google-api-python-client`, `google-auth` (см. `requirements.txt`).

---

## 6. Ошибки

При сбое upload в Drive экспорт **не падает**: PDF stream отдаётся, в лог — warning; локальный cache (если включён) сохраняется.

---

## 7. Workspace UI (не противоречит prod)

| Элемент | Назначение |
|---------|------------|
| `/status` → `storage_label`, `gdrive_configured` | строка «Хранилище отчётов» для админа |
| Модалка сессии | ссылка «Открыть отчёт» если `report.pdf_ref` |
| После export PDF | заголовки `X-Psych-Pdf-Ref`, `X-Psych-Pdf-Open-Url` + ссылка в модалке |
| `response_mode=json` | поля `pdf_open_url`, `storage_kind` |

UI и Drive upload **дополняют** друг друга: без prod-настройки статус покажет «не настроено», ссылки появятся после успешного export.

---

## 8. Чеклист prod (первый export)

1. **GCP:** проект → IAM → Service Account → ключ JSON → скачать.
2. **Drive:** папка → Share → email SA (`...@....iam.gserviceaccount.com`) → Editor.
3. **Секреты:** JSON в `secrets/` (в `.gitignore`), **не коммитить**.
4. **`.env`:**
   ```bash
   PSYCH_TESTING_GDRIVE=1
   PSYCH_TESTING_GDRIVE_FOLDER_ID=<id из URL папки>
   GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=secrets/psych-testing-sa.json
   PSYCH_TESTING_PERSIST_JSON=1
   PSYCH_TESTING_PDF_CACHE=hash
   ```
5. **Проверка:** HR export PDF → файл в Drive `{date}/{client_name}/` (например `2026-05-21/TOO_Vtoroe/`) → в session JSON `report.pdf_ref`: `gdrive:...` → в Workspace ссылка «Открыть в Google Drive».

**Структура на Shared Drive** (корень = `PSYCH_TESTING_GDRIVE_FOLDER_ID`, например общий диск `PsychTest Rep2026`):

```
PsychTest Rep2026/
  2026-05-21/
    TOO_Vtoroe/          ← clients.name, транслит (ТОО Второе)
    TOO_Odin/            ← ТОО Один
    TOO_Beta/            ← ТОО_Бета
      Kim_Sergey_Vasilevich_….pdf
      {manifest_id}_manifest.json
```

Имя папки берётся из **`clients.name`** в HR (как на экране «Клиенты (организации)»); при отсутствии — `clients.code`, затем `client_id`. Локальный кэш использует те же транслит-имена: `{client_name_slug}/{date}/` под `data/report_exports/` (старые папки по `client_id` по-прежнему находятся при чтении кэша).

---

## 9. Связанные документы

- [08_RBAC_STORAGE_VERSIONING.md](08_RBAC_STORAGE_VERSIONING.md) — platform storage (Phase 4 DB)
- [16_PDF_EXPORT_CONTRACT_AND_PLAN.md](16_PDF_EXPORT_CONTRACT_AND_PLAN.md) — PDF contract
- [11_TECHNICAL_DEBT.md](11_TECHNICAL_DEBT.md) — D18 legacy OAuth

---

## 10. Expose headers (CORS)

Если Workspace на другом origin, для чтения `X-Psych-*` из `fetch` может понадобиться `expose_headers` в FastAPI/CORS — при same-origin (типичный деплой) не требуется.

---

## 11. Windows prod (UNC + service account)

На Windows-сервере JSON ключ часто лежит на сетевой шаре, а не в каталоге приложения:

```env
PSYCH_TESTING_GDRIVE=1
PSYCH_TESTING_GDRIVE_FOLDER_ID=<Shared Drive root id>
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=\\fileserver\hr-secrets\psych-testing-sa.json
PSYCH_TESTING_PERSIST_JSON=1
PSYCH_TESTING_PERSIST_DB=1
PSYCH_TESTING_PDF_CACHE=hash
```

Проверки:

1. Учётная запись **службы IIS / worker / uvicorn** должна иметь **Read** на UNC-путь к JSON.
2. Папка Drive расшарена на email SA (`...@....iam.gserviceaccount.com`) с ролью **Editor** (или Content manager на Shared Drive).
3. Локальная проверка конфигурации (без upload):

   ```bash
   python scripts/verify_psych_gdrive.py
   python scripts/verify_psych_gdrive.py --probe
   ```

4. Smoke после деплоя: HR export PDF → файл в `{date}/{client_name}/` на Drive → `report.pdf_ref`: `gdrive:...` в session JSON.

Inline JSON (`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_INLINE`) — альтернатива UNC для Docker/K8s secrets.
