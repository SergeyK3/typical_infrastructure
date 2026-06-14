<!-- docs/runbook/DEV_DEPLOYMENT.md -->
# Runbook: Dev-развёртывание

## Назначение

Инструкция по развёртыванию Typical infrastructure MVP в dev-окружении.

## Требования

- Python 3.11+
- pip

## Шаги развёртывания

### 1. Клонирование и подготовка окружения

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# или: source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
```

### 2. Конфигурация (опционально)

Создайте `.env` в корне проекта при необходимости:

```env
APP_NAME=Typical infrastructure
SQLITE_PATH=app.db
```

По умолчанию используется SQLite в файле `app.db`.

### 3. Запуск приложения

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

Сервис будет доступен по адресу `http://127.0.0.1:8100`.

### 4. Проверка готовности

```bash
curl http://127.0.0.1:8100/health/ready
```

Ожидаемый ответ: `{"status": "ready", "service": "Typical infrastructure"}`.

### 5. OpenAPI документация

- Swagger UI: http://127.0.0.1:8100/docs
- ReDoc: http://127.0.0.1:8100/redoc

### 6. UI Wizard

Мастер one-click onboarding: http://127.0.0.1:8100/wizard

## При запуске

1. При старте создаётся БД (если отсутствует) и выполняются миграции.
2. seed-данные (роли, шаблоны) загружаются автоматически.
3. При первом запуске создаётся `app.db` в текущей директории.

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| Порт 8100 занят | Задайте другой `--port` (например `8000` для второго проекта) или измените `APP_PORT` в `.env` | 
| Ошибка импорта | Проверьте активацию venv и `pip install` |
| Ошибка БД | Удалите `app.db` и перезапустите (данные будут потеряны) |

## См. также

- [Seed и демо-сценарии](SEED_AND_DEMO.md)
- [Матрица фаза → endpoint → экран → тест](../backlog/PHASE_ENDPOINT_MATRIX.md)
