# Runbook: Staging / Pilot Deployment

## Назначение

Развёртывание Typical infrastructure MVP на staging (пилотный стенд) для smoke-проверок и сбора обратной связи.

## Требования

- Docker и Docker Compose
- Доступ к порту 8000 (или настраиваемому)

## Быстрый старт

```bash
# Клонирование (если ещё не сделано)
git clone <repo> && cd 10_Typical_infrastructure

# Сборка и запуск
docker compose up -d --build

# Проверка
curl http://localhost:8000/health/ready
```

## Smoke-проверка после деплоя

```bash
# Python (кросс-платформенно)
python scripts/smoke_check.py --url http://localhost:8000

# Или вручную
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/clients
curl http://localhost:8000/api/enterprise-templates
curl http://localhost:8000/wizard
```

Ожидаемый результат smoke_check: все проверки `OK`.

## Доступные эндпоинты

| URL | Описание |
|-----|----------|
| http://localhost:8000/health/ready | Readiness probe |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/wizard | UI-мастер onboarding |
| http://localhost:8000/api/* | REST API |

## Данные

- SQLite БД хранится в Docker volume `app_data`
- Seed (роли, шаблоны) загружается при первом старте
- См. [SEED_AND_DEMO.md](SEED_AND_DEMO.md) для демо-сценариев

## Остановка

```bash
docker compose down
# С сохранением данных (volume остаётся)
docker compose down -v  # удалить данные
```

## См. также

- [Production-like deployment](PRODUCTION_LIKE_DEPLOYMENT.md) — Docker, env, secrets
- [Dev deployment](DEV_DEPLOYMENT.md) — локальная разработка
