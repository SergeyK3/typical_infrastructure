# Backlog Work Steps

Master structure for backlog execution. Open this file to see all steps in the left sidebar outline.

---

## Step 1 — Foundation & Master Data

Phase 1 scope. See `mvp_backlog_by_phases.md` §4.

- API foundation, clients, templates, roles
- Baseline schema and CRUD

---

## Step 2 — Org Structure & Workforce Core

Phase 2 scope. See `mvp_backlog_by_phases.md` §5.

- Org-units, positions, employees
- Tree and bulk endpoints

---

## Step 3 — Accounts, Roles & Access Readiness

Phase 3 scope. See `mvp_backlog_by_phases.md` §6.

- Accounts CRUD, role assignment
- Password/reset placeholder

---

## Step 4 — One-click Onboarding Orchestration

Phase 4 scope. See `mvp_backlog_by_phases.md` §7.

- Bootstrap endpoint
- Onboarding run model and steps
- Basic dry-run

---

## Step 5 — Backlog tasks (short)

Contract hardening and documentation for onboarding runs.

**Документация Step 5:**
- [Idempotency policy](../onboarding/onboarding_idempotency_policy.md)
- [Dry-run contract](../onboarding/onboarding_dry_run_contract.md)
- [Statuses and error codes](../onboarding/onboarding_statuses_and_error_codes.md)
- [API Reference](../onboarding/onboarding_api_reference.md)

### [STEP5-1] Define idempotency policy for onboarding

Describe semantics of `idempotency_key`, allowed retry scenarios per run status (pending/completed/failed/dry_run), and expected API behavior on duplicate keys.

**Done:** `../onboarding/onboarding_idempotency_policy.md`

### [STEP5-2] Implement idempotent behavior in onboarding orchestration

Add lookup by `idempotency_key`, decide on unique index, and implement consistent handling of concurrent/duplicate requests (reuse existing run vs return 409).

**Done:** `app/onboarding.py`, `app/models.py`, `app/routers/onboarding.py`

### [STEP5-3] Finalize dry-run behavior contract

Precisely define which validations are executed, which steps are marked skipped, final run status for dry-run, and how clients should interpret dry-run results.

**Done:** `../onboarding/onboarding_dry_run_contract.md`

### [STEP5-4] Normalize statuses and error codes for onboarding

Freeze the list of allowed OnboardingRun / OnboardingStep statuses and standardize `error_code` values for typical failure cases.

**Done:** `app/onboarding_constants.py`, `../onboarding/onboarding_statuses_and_error_codes.md`

### [STEP5-5] Update API documentation for onboarding runs

Reflect idempotency, dry-run, statuses and error codes in API docs/OpenAPI, including example flows for retry, conflict, and dry-run-before-real-run.

**Done:** `../onboarding/onboarding_api_reference.md`, `../specs/open_api_baseline_v_1_mvp.md`

---

## Step 6 — UI Wizard, Polish & MVP Hardening

Phase 5 scope. See `mvp_backlog_by_phases.md` §8.

Цель: сделать продукт пригодным для реального использования операторами внедрения.

**Документация Phase 5:** [mvp_backlog_by_phases.md §8](mvp_backlog_by_phases.md) — scope, user stories, acceptance criteria.

### [STEP6-1] UI-мастер one-click onboarding

Реализовать мастер из шагов: выбор шаблона → данные клиента → оргструктура → должности → сотрудники → аккаунты → подтверждение → dry-run/run → прогресс и результат.

- Сохранение состояния формы (черновик)
- Field-level validation
- User-friendly тексты ошибок
- Предотвращение повторного запуска

**Done:** `static/wizard/index.html`, `app/routers/enterprise_templates.py`, `/wizard`, `/api/enterprise-templates`, `/api/enterprise-templates/{id}/structure-preview`

### [STEP6-2] Backend hardening

- Более полные validation messages
- Traceability run-to-entities
- Улучшенные run logs
- Защита от некорректных payload на boundary API

**Done:** `app/schemas.py` (extra=forbid, validation messages), `app/models.py` (created_entities), `app/main.py` (validation exception handler), `app/onboarding.py` (user-friendly error detail)

### [STEP6-3] QA / Testing

- Smoke tests по фазам
- Интеграционные тесты onboarding
- Тесты dry-run
- Тесты идемпотентности
- Тесты ошибок по несогласованным ссылкам

**Done:** `tests/test_smoke.py`, `tests/test_onboarding_integration.py`, `tests/test_onboarding_dry_run.py`, `tests/test_onboarding_idempotency.py`, `tests/test_onboarding_errors.py`

---

## Step 7 — Production Readiness & Observability

Post-MVP scope. See `mvp_backlog_by_phases.md` §9 (сквозные задачи).

Цель: подготовить продукт к пилотному развёртыванию и обеспечить наблюдаемость.

### [STEP7-1] Request tracing & logging

- request_id / trace_id в заголовках и логах
- Базовые логи сервиса (request, response status)
- Логи ключевых orchestration-шагов (run_id, step_code, status)

**Done:** `app/logging_middleware.py`, `app/main.py`, `app/onboarding.py`

### [STEP7-2] API consistency & documentation

- Единый error envelope (формат ошибок)
- Пагинация: единый формат limit/offset
- OpenAPI spec в актуальном состоянии
- Матрица фаза → endpoint → экран → тест

**Done:** `app/error_envelope.py`, `app/main.py`, `docs/backlog/PHASE_ENDPOINT_MATRIX.md`

### [STEP7-3] Runbook & deployment

- Runbook по dev-развёртыванию
- Инструкция по seed и демо-сценариям
- Health check (readiness) endpoint

**Done:** `app/main.py` (`GET /health/ready`), `docs/runbook/DEV_DEPLOYMENT.md`, `docs/runbook/SEED_AND_DEMO.md`

---

## Step 8 — Pilot Deployment & Post-MVP Roadmap

Post-MVP. See `mvp_backlog_by_phases.md` §13.

Цель: развёртывание пилота и определение приоритетов развития.

### [STEP8-1] Pilot deployment

- Развёртывание на staging / пилотный стенд
- Инструкция по production-like развёртыванию (Docker, env, secrets)
- Smoke-проверка после деплоя

**Done:** `Dockerfile`, `docker-compose.yml`, `.env.example`, `docs/runbook/STAGING_DEPLOYMENT.md`, `docs/runbook/PRODUCTION_LIKE_DEPLOYMENT.md`, `scripts/smoke_check.py`

### [STEP8-2] Feedback & stabilization

- Сбор обратной связи от пилотных пользователей
- Фиксация багов и доработок
- Стабилизация перед расширением

**Done:** `docs/backlog/STEP8_FEEDBACK_TEMPLATE.md`

### [STEP8-3] Post-MVP roadmap (из §13)

Приоритизация направлений:

- расширенный RBAC;
- импорт из внешних HR-источников;
- события и уведомления;
- каталог компетенций;
- assessment / диагностика;
- learning plans;
- KPI / performance integration.

**Done:** `docs/backlog/POST_MVP_ROADMAP.md`

---

## Step 9 — MVP Expansion: Client Workspace (Управление организацией)

Цель: интерфейс «внутри» организации — просмотр и редактирование подразделений, должностей, сотрудников, аккаунтов. API уже есть, нужен UI.

### [STEP9-1] Страница «Рабочее пространство клиента»

- Маршрут `/client/{client_id}` или `/workspace?client_id=...`
- Выбор клиента из списка (или переход со страницы /clients)
- Шапка с названием организации, навигация по разделам

### [STEP9-2] Подразделения (org-units)

- Просмотр дерева подразделений (расширить текущий вид на /clients)
- Кнопка «Добавить подразделение»: форма (код, название, родитель, тип)
- Редактирование существующего подразделения
- API: `POST /api/org-units`, `PATCH /api/org-units/{id}`

### [STEP9-3] Должности (positions)

- Список должностей клиента
- Добавление должности: код, название, подразделение (org_unit_id)
- API: `POST /api/positions`, `GET /api/positions?client_id=...`

### [STEP9-4] Сотрудники (employees)

- Список сотрудников клиента
- Добавление сотрудника: ФИО, email, подразделение, должность
- API: `POST /api/employees`, `GET /api/employees?client_id=...`

### [STEP9-5] Аккаунты (accounts)

- Список аккаунтов клиента (логин, сотрудник, роли)
- Добавление аккаунта: привязка к сотруднику, логин, пароль, роли
- API: `POST /api/accounts`, `GET /api/accounts?client_id=...`

### [STEP9-6] Навигация и интеграция

- Ссылка «Войти в организацию» на странице /clients при клике на карточку
- Обратная навигация: «← К списку клиентов»

---

## Step 10 — Клиенты: список организаций и демо-данные

Цель: раздел «Клиенты» в верхней части сайдбара — при клике показывать полный список всех организаций. Добавить seed с 7–8 демо-организациями.

### [STEP10-1] Seed клиентов (демо-организации)

- Добавить `seed_clients()` в `app/seed.py` с 7–8 организациями (ТОО Альфа, ИП Бета, Impl 3 Demo LLC и т.п.)
- Вызывать в `seed_all()`

### [STEP10-2] Страница «Клиенты» — полный список

- `/clients` — загрузка через `GET /api/clients`, карточки организаций
- Клик по карточке → `/client/{client_id}`

### [STEP10-3] Проверка UX

- При первом запуске в списке 7–8 организаций
- Пустое состояние: подсказка «Создать через мастер onboarding»
