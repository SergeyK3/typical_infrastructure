# Runbook: Production-like Deployment

## Назначение

Инструкция по production-like развёртыванию Typical infrastructure MVP: Docker, переменные окружения, secrets.

Источник: [BACKLOG_STEPS.md](../backlog/BACKLOG_STEPS.md) STEP8-1.

---

## 1. Docker

### Сборка образа

```bash
docker build -t typical-infra-mvp:latest .
```

### Запуск контейнера

```bash
docker run -d \
  --name typical-infra \
  -p 8100:8000 \
  -e APP_NAME="Typical infrastructure" \
  -e SQLITE_PATH=/app/data/app.db \
  -v typical_data:/app/data \
  typical-infra-mvp:latest
```

### Docker Compose (рекомендуется)

```bash
cp .env.example .env
# Отредактируйте .env при необходимости
docker compose up -d --build
```

---

## 2. Переменные окружения (env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `APP_NAME` | Имя сервиса | Typical infrastructure |
| `SQLITE_PATH` | Путь к SQLite БД | app.db (в контейнере: /app/data/app.db) |
| `APP_PORT` | Хост-порт (compose / браузер) | 8100 |

### Файл .env

Создайте `.env` в корне проекта (не коммитить в git):

```env
APP_NAME=Typical infrastructure
SQLITE_PATH=/app/data/app.db
APP_PORT=8100
```

---

## 3. Secrets (рекомендации)

Текущий MVP использует SQLite без паролей. Для production-like окружения:

### Что хранить в secrets

- **Будущее**: при переходе на PostgreSQL — `DATABASE_URL` с паролем
- **Будущее**: API keys, JWT secrets — через секреты оркестратора

### Текущая практика

- `.env` — не коммитить, добавить в `.gitignore`
- Для Docker: передавать через `-e` или docker secrets
- Для Kubernetes: использовать Secret objects

### Пример с docker secret (Docker Swarm)

```bash
echo "my_secret_value" | docker secret create app_secret -
# Использование в stack/compose
```

---

## 4. Health check

Readiness endpoint:

```bash
curl http://localhost:8100/health/ready
# {"status":"ready","service":"Typical infrastructure"}
```

Используйте в оркестраторах (K8s readinessProbe, Docker healthcheck).

---

## 5. Smoke-проверка после деплоя

```bash
python scripts/smoke_check.py --url http://<your-host>:8100
```

Или для удалённого staging:

```bash
python scripts/smoke_check.py --url https://staging.example.com
```

### Psychological testing (Phase 4a)

На **prod-сервере** (доступ к `.env`, UNC, `app.db`):

```powershell
.\scripts\probe_psych_prod.ps1
```

Удалённо (только конфиг + RBAC denial):

```bash
python scripts/smoke_psych_pilot.py --url https://<host> --status-only
```

Полный чеклист: [PSYCH_PROD_DEPLOY.md](PSYCH_PROD_DEPLOY.md).

---

## 6. Ограничения MVP

- SQLite — один инстанс, без репликации
- Нет встроенной аутентификации API (добавить на следующем этапе)
- Статика и API в одном процессе

---

## См. также

- [STAGING_DEPLOYMENT.md](STAGING_DEPLOYMENT.md)
- [DEV_DEPLOYMENT.md](DEV_DEPLOYMENT.md)
- [BACKLOG_STEPS.md](../backlog/BACKLOG_STEPS.md) Step 8
