## Typical infrastructure (MVP backend)

**Текущая версия ядра:** см. файл [`VERSION`](VERSION). Релизы в Git помечаются тегами (`v1.0.0`, …).

### Run

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

**Важно — номер порта:** по умолчанию проект использует **`8100`** (см. `APP_PORT` в `.env` / `.env.example`). В браузере открывайте **`http://127.0.0.1:8100/`**. Docker Compose пробрасывает тот же хост-порт: `${APP_PORT:-8100}` → `8000` внутри контейнера.

Open docs at `http://127.0.0.1:8100/docs`. UI wizard: `http://127.0.0.1:8100/wizard`. Рабочее пространство клиента: `http://127.0.0.1:8100/client/{client_id}`.

**Порт 8080** — только если вы **отдельно** запускаете `.\run_http_8080.ps1` (например, когда второй проект уже занял 8100). Порт в адресе браузера и порт в команде запуска должны совпадать.

Если по **`localhost`** соединение не устанавливается, а сервер точно запущен, попробуйте **`127.0.0.1`** вместо `localhost` (на Windows имя иногда резолвится в IPv6 `::1`, куда процесс может не слушать).

### REST (что означает аббревиатура)

**REST** — *Representational State Transfer* (передача состояния представления). Это соглашение о том, как делать **веб-API поверх HTTP**: сущности предстают как **ресурсы** с понятными URL (например `/api/clients`, `/api/regulations/{code}`), с ними работают стандартные **методы** (`GET` — прочитать, `POST` — создать, `PATCH` — частично изменить, `DELETE` — удалить), тело запроса/ответа чаще всего **JSON**. Сервер не хранит «сессию приложения» между запросами в смысле протокола: каждый запрос содержит достаточно контекста (заголовки, токен и т.д., если вы их добавите). В этом проекте HTTP-эндпоинты под `/api/...` — пример такого **RESTful** API; интерактивное описание — в Swagger по адресу `/docs`.

### Run with HTTPS (fixes "attribution reporting origins are trustworthy")

```powershell
.\run_https.ps1
```

Or manually:
```bash
python scripts/gen_ssl_cert.py
python -m uvicorn app.main:app --reload --ssl-keyfile=.dev/key.pem --ssl-certfile=.dev/cert.pem
```

Then open **https://127.0.0.1:8100** (accept the self-signed cert warning once).

Health check: `GET /health/ready` — readiness probe for deployment.

### Справочники: глобальные и данные организации

Описание разделения (флаги `is_detached`, `catalog_source_code`, модель `ClientPositionRegulation`): **[docs/architecture/reference_catalogs_global_and_client.md](docs/architecture/reference_catalogs_global_and_client.md)**.

Пользовательское руководство (несколько ординаторов / ставок, схема для скриншота): **[docs/guides/](docs/guides/)** — [Markdown](docs/guides/руководство_должности_тип_и_ставки.md), [HTML в браузере](docs/guides/руководство_должности_тип_и_ставки.html).

Копии на стороне клиента (через `/docs`): `POST /api/client-regulations/copy-from-global`, `POST /api/positions/from-catalog`, `POST /api/org-units/from-template-node`.

### Tests

```bash
python -m pytest tests/ -v
```

### One-click bootstrap (Windows)

```powershell
.\bootstrap.ps1
```

### Onboarding runs (Phase 3)

`POST /api/onboarding-runs` — создаёт заказчика, оргструктуру, должности, админ-сотрудника и **учётную запись** с ролью `admin`.

Пример payload:

```json
{
  "template_code": "default",
  "client": { "code": "acme", "name": "ACME LLC" },
  "admin": {
    "last_name": "Иванов",
    "first_name": "Иван",
    "login": "admin@acme.test",
    "password": "TempPass123!",
    "email": "admin@acme.test"
  }
}
```

- `admin.login` — обязателен, уникален в системе.
- `admin.password` — опционален; если не указан, генерируется временный пароль.

`GET /api/onboarding-runs/{run_id}` — статус run и шаги (включая `create_admin_account`).

### Accounts (Phase 3)

- `GET /api/accounts?client_id=...` — список аккаунтов клиента
- `POST /api/accounts` — создать аккаунт
- `POST /api/accounts/{account_id}/reset-password` — сброс пароля (генерация временного)
