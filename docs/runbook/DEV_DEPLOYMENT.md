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
python -m uvicorn app.main:app --reload
```

Сервис будет доступен по адресу `http://127.0.0.1:8000`.

### 4. Проверка готовности

```bash
curl http://127.0.0.1:8000/health/ready
```

Ожидаемый ответ: `{"status": "ready", "service": "Typical infrastructure"}`.

### 5. OpenAPI документация

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 6. UI Wizard

Мастер one-click onboarding: http://127.0.0.1:8000/wizard

## При запуске

1. При старте создаётся БД (если отсутствует) и выполняются миграции.
2. seed-данные (роли, шаблоны) загружаются автоматически.
3. При первом запуске создаётся `app.db` в текущей директории.

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| Порт 8000 занят | Используйте `--port 8001` | 
| Ошибка импорта | Проверьте активацию venv и `pip install` |
| Ошибка БД | Удалите `app.db` и перезапустите (данные будут потеряны) |

## См. также

- [Seed и демо-сценарии](SEED_AND_DEMO.md)
- [Матрица фаза → endpoint → экран → тест](../backlog/PHASE_ENDPOINT_MATRIX.md)
