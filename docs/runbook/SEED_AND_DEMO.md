<!-- docs/runbook/SEED_AND_DEMO.md -->
# Seed и демо-сценарии

## Назначение

Описание seed-данных и типовых демо-сценариев для Typical infrastructure MVP.

## Seed-данные (автоматически при старте)

### Роли

- `admin` — Administrator
- `hr` — HR
- `manager` — Manager
- `employee` — Employee

### Шаблоны предприятий

- `default` — Default enterprise template (версия 1, baseline)

### Клиенты (демо-организации)

При первом запуске создаются 8 организаций:

- ТОО Альфа, ИП Бета, АО Гамма, ТОО Демо ACME, Impl 3 Demo LLC, ТОО Дельта, ИП Эпсилон, ООО Сигма

## Демо-сценарий 1: One-click onboarding

Полный запуск через API:

```bash
curl -X POST "http://127.0.0.1:8000/api/onboarding-runs" \
  -H "Content-Type: application/json" \
  -d '{
    "template_code": "default",
    "client": {
      "code": "demo_acme",
      "name": "ТОО Демо ACME"
    },
    "admin": {
      "last_name": "Admin",
      "first_name": "System",
      "login": "admin@demo.test",
      "password": "TempPass123!",
      "email": "admin@demo.test"
    }
  }'
```

### Dry-run (без создания сущностей)

```bash
curl -X POST "http://127.0.0.1:8000/api/onboarding-runs?dry_run=true" \
  -H "Content-Type: application/json" \
  -d '{
    "template_code": "default",
    "client": {"code": "dry_run_client", "name": "Dry Run Client"},
    "admin": {
      "last_name": "A", "first_name": "B",
      "login": "dry_admin", "password": "x", "email": null
    }
  }'
```

### Проверка статуса run

```bash
curl "http://127.0.0.1:8000/api/onboarding-runs/{run_id}"
```

## Демо-сценарий 2: Через UI Wizard

1. Откройте http://127.0.0.1:8000/wizard
2. Выберите шаблон `default`
3. Введите данные клиента (код, название)
4. Просмотрите оргструктуру и должности
5. Введите данные администратора
6. Запустите dry-run или реальный run
7. Просмотрите прогресс и результат

## Демо-сценарий 3: Идемпотентность

Повторный запрос с тем же `Idempotency-Key` и payload возвращает существующий run:

```bash
KEY="demo-idem-001"
curl -X POST "http://127.0.0.1:8000/api/onboarding-runs" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $KEY" \
  -d '{
    "template_code": "default",
    "client": {"code": "idem_client", "name": "Idem Client"},
    "admin": {"last_name": "A", "first_name": "B", "login": "idem_admin", "password": "x", "email": null}
  }'

# Повторный тот же запрос — вернёт тот же run_id
curl -X POST "http://127.0.0.1:8000/api/onboarding-runs" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $KEY" \
  -d '...'
```

## Демо-сценарий 4: Проверка созданных сущностей

После успешного onboarding:

```bash
# Список клиентов
curl "http://127.0.0.1:8000/api/clients"

# Оргструктура клиента
curl "http://127.0.0.1:8000/api/org-units?client_id={client_id}"

# Должности
curl "http://127.0.0.1:8000/api/positions?client_id={client_id}"

# Сотрудники
curl "http://127.0.0.1:8000/api/employees?client_id={client_id}"

# Аккаунты
curl "http://127.0.0.1:8000/api/accounts?client_id={client_id}"
```

## Сброс данных

Для чистого старта удалите `app.db` и перезапустите приложение. Seed-данные загрузятся заново.
