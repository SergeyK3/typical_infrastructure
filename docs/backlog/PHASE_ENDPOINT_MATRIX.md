<!-- docs/backlog/PHASE_ENDPOINT_MATRIX.md -->
# Матрица: фаза → endpoint → экран → тест

## Назначение

Сводная таблица покрытия MVP по фазам: endpoint'ы, экраны UI, тесты.

## Формат

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| ... | ... | ... | ... |

---

## Phase 1 — Foundation & Master Data

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| 1 | `GET /api/clients` | Список клиентов | `test_clients_list` |
| 1 | `GET /api/clients/{id}` | Карточка клиента | — |
| 1 | `POST /api/clients` | Форма создания | — |
| 1 | `PATCH /api/clients/{id}` | Редактирование | — |
| 1 | `GET /api/enterprise-templates` | Список шаблонов | `test_enterprise_templates_list` |
| 1 | `GET /api/enterprise-templates/{id}` | Детали шаблона | `test_enterprise_template_detail` |
| 1 | `GET /api/enterprise-templates/{id}/structure-preview` | Preview структуры | `test_structure_preview` |

---

## Phase 2 — Org Structure & Workforce Core

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| 2 | `GET /api/org-units?client_id=` | Дерево оргструктуры | `test_org_units_requires_client_id` |
| 2 | `GET /api/org-units/tree?client_id=` | Дерево | — |
| 2 | `POST /api/org-units` | Форма создания | — |
| 2 | `PATCH /api/org-units/{id}` | Редактирование | — |
| 2 | `POST /api/org-units/bulk` | Bulk | — |
| 2 | `GET /api/positions?client_id=` | Список должностей | `test_positions_requires_client_id` |
| 2 | `POST /api/positions` | Форма | — |
| 2 | `PATCH /api/positions/{id}` | Редактирование | — |
| 2 | `POST /api/positions/bulk` | Bulk | — |
| 2 | `GET /api/employees?client_id=` | Список сотрудников | `test_employees_list` |
| 2 | `POST /api/employees` | Форма | — |
| 2 | `GET /api/employees/{id}` | Карточка | — |
| 2 | `PATCH /api/employees/{id}` | Редактирование | — |
| 2 | `POST /api/employees/bulk` | Bulk | — |

---

## Phase 3 — Accounts, Roles & Access

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| 3 | `GET /api/accounts?client_id=` | Список аккаунтов | `test_accounts_list` |
| 3 | `POST /api/accounts` | Форма создания | — |
| 3 | `PATCH /api/accounts/{id}` | Редактирование | — |
| 3 | `POST /api/accounts/bulk` | Bulk | — |
| 3 | `POST /api/accounts/{id}/reset-password` | Сброс пароля | — |

---

## Phase 4 — One-click Onboarding Orchestration

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| 4 | `POST /api/onboarding-runs` | Запуск | `test_onboarding_integration`, `test_dry_run_*` |
| 4 | `GET /api/onboarding-runs` | Список runs | `test_onboarding_runs_list` |
| 4 | `GET /api/onboarding-runs/{id}` | Статус run | `test_onboarding_integration` |
| 4 | `GET /api/onboarding-runs/{id}/steps` | — (включено в run) | — |

---

## Phase 5 — UI Wizard & Hardening

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| 5 | `GET /wizard` | Мастер onboarding | — |
| 5 | `GET /api/enterprise-templates` | Шаг 1: выбор шаблона | — |
| 5 | `GET /api/enterprise-templates/{id}/structure-preview` | Шаг 2–3: оргструктура | — |
| 5 | `POST /api/onboarding-runs` | Шаг 7–8: dry-run/run | — |

---

## Step 7 — Production Readiness

| Фаза | Endpoint | Экран | Тест |
|------|----------|-------|------|
| 7 | `GET /health/ready` | — | — |
| 7 | `X-Request-Id`, `X-Trace-Id` | — | — |
| 7 | Error envelope `error.code`, `error.message` | — | `test_onboarding_errors`, `test_onboarding_idempotency` |

---

## Пагинация (единый формат)

Все list-эндпоинты используют `limit` и `offset`:

- `GET /api/clients?limit=50&offset=0`
- `GET /api/org-units?client_id=...&limit=50&offset=0`
- `GET /api/positions?client_id=...&limit=50&offset=0`
- `GET /api/employees?client_id=...&limit=50&offset=0`
- `GET /api/accounts?client_id=...&limit=50&offset=0`
- `GET /api/onboarding-runs?limit=50&offset=0`

Формат ответа: `{"items": [...], "total": N, "limit": 50, "offset": 0}`.
