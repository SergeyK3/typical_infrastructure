# PROJ-PERSON Assessment

| Поле | Значение |
|------|----------|
| **Проект** | PROJ-PERSON — Phase A (Core HR Foundation) |
| **Дата** | 2026-06-30 |
| **Статус** | Assessment (без реализации) |
| **Основание** | [ARCHITECTURE_GOVERNANCE](../ARCHITECTURE_GOVERNANCE.md), [ADR-049](../adr/ADR-049-administrative-roles-and-responsibility-model.md), [ADR-050](../adr/ADR-050-personnel-lifecycle-architecture.md), [ADR-051](../adr/ADR-051-personnel-order-workflow-architecture.md), [HR Domain Glossary](../reference/hr-domain-glossary.md), [HR Contour Implementation Roadmap](../roadmap/hr-contour-implementation-roadmap.md) |

---

## Executive Summary

В текущей кодовой базе **сущность Person отсутствует**. Роль identity aggregate de facto выполняет **монолитный `Employee`**: на нём хранятся ФИО, контакты, org/position, статус занятости; `employee.id` используется как якорь идентичности во всей платформе (Account, HR-модули, Telegram, consent, psych testing, skill assessment).

Это **системное расхождение** с ADR-049/050:

```text
Target:  Person → Employee → Employment → …
As-Is:   Employee (monolith) → Account
```

**PROJ-PERSON** — первый шаг Phase A: ввести Person и связать `Employee.person_id`, не ломая существующих потребителей `employee_id`. Объём затронут ~**90+ файлов** с `employee_id`; непосредственно Phase 1 затронет **ядро** (~6–10 файлов), остальное — последующие этапы.

**Оценка сложности Phase 1 (только Person + link):** **Medium** (3–5 dev-days) **при условии, что физическая модель Person и политика миграции зафиксированы в Accepted ADR или в дополнительном архитектурном документе (при необходимости).**

**Оценка полного приведения к target-модели (Person + Employment + Events):** **High** (multi-sprint, cross-module).

**Критический вывод:** миграция должна быть **additive и backward-compatible**: Person создаётся «в тени», затем backfill, затем обязательность `person_id`, и только потом — перенос полей и read-path.

### Архитектурная оговорка (физическая модель и миграция)

> Может потребоваться дополнительный архитектурный документ, определяющий физическую модель Person и политику миграции, если эти вопросы не будут полностью закрыты существующими Accepted ADR (ADR-049, ADR-050, ADR-051).

---

## 1. Текущее состояние реализации

### 1.1. Существует ли Person?

| Вопрос | Ответ |
|--------|-------|
| Модель `Person` в коде | **Нет** |
| Таблица `persons` в `app/models.py` | **Нет** |
| API `/api/persons` | **Нет** |
| `Employee.person_id` | **Нет** |

**Примечание:** скрипт `scripts/audit_bind_code.py` опционально проверяет таблицу `persons` в SQLite — это **legacy/dev-проверка**, не каноническая схема репозитория.

### 1.2. Какие сущности выполняют роль Person?

**`Employee`** — единственный носитель identity-данных (`app/models.py`: `last_name`, `first_name`, `middle_name`, `email`, `phone`, `telegram_id`).

Дополнительно identity косвенно «размазана» по:

- **`Account.login`** — технический идентификатор доступа (не Person, ADR-049 INV-13).
- **Import dedup** в `app/routers/employees.py` — по `(client_id, email)` и `(client_id, FIO)` на `employees`, без Person-level dedup (OQ-50-1).

### 1.3. Таблицы, относящиеся к Person (as-is / target)

| Таблица | As-Is | Target |
|---------|-------|--------|
| `persons` | **Отсутствует** | Identity aggregate (ADR-050 §3.1) |
| `employees` | Хранит Person + Employment + status | Только aggregate root: `person_id`, `employee_code`, aggregate status |
| `employee_consent_records` | `(client_id, employee_id)` | Остаётся на Employee; PII — Person (Phase B+) |
| HR-модули (`pt_*`, `sa_*`) | `employee_id` | `employee_id` + опционально `person_id` (INV-15) |

### 1.4. Модели, относящиеся к Person

| Модуль | Модель | Связь с identity |
|--------|--------|------------------|
| `app/models.py` | `Employee` | **De facto Person + Employee** |
| `app/schemas.py` | `EmployeeBase`, `EmployeeCreate`, `EmployeePatch`, `EmployeeOut` | Person-поля в Employee DTO |
| `skill_assessment/integration/hr_core.py` | `EmployeeSnapshot` | Duck-typing полей Employee |
| `psychological_testing/integration/hr_core.py` | `EmployeeSnapshot` | ФИО + `telegram_id` из Employee |

### 1.5. API, использующие Person-подобные данные

| Endpoint | Person-подобные операции |
|----------|--------------------------|
| `GET/POST/PATCH/DELETE /api/employees` | CRUD ФИО, контактов, org, status |
| `POST /api/employees/import-excel` | Массовое создание/обновление по FIO/email |
| `POST /api/employees/bulk` | Upsert с Person+Employment полями |
| `GET /api/employees/export/excel` | Экспорт всех полей Employee |
| `GET/POST /api/accounts` | Привязка к `employee_id` |
| `/api/psychological-testing/employees/{id}/*` | Display name, export из Employee |
| Skill assessment routes | `employee_id` в сессиях, examination, Telegram |

### 1.6. Сервисы, использующие Person-подобные данные

| Сервис / модуль | Использование |
|-----------------|---------------|
| `app/routers/employees.py` | Основной CRUD identity + org |
| `app/onboarding.py` | Создание admin Employee при onboarding |
| `app/auth/context.py` | `client_id` через `Account → Employee` |
| `app/auth/tenant.py` | `load_employee_for_ctx` |
| `app/hr.py` | In-process HR bridge для skill assessment |
| `app/services/employee_consent.py`, `telegram_employee_consent.py` | Consent по `employee_id` |
| `app/services/psych_*` | Assignments, sessions, RBAC, Telegram |
| `skill_assessment/*`, `psychological_testing/*` | ~50+ файлов с `employee_id` |
| `app/client_template_dedup.py`, `app/org_unit_ops.py` | Reassign org/position на Employee |

---

## 2. Анализ Employee: поля Person vs Employee vs будущие сущности

| Поле (as-is) | Фактическая роль | Target-сущность | Действие |
|--------------|------------------|-----------------|----------|
| `id` | PK, identity anchor системы | **Employee** | Сохранить (INV-2) |
| `client_id` | Tenant scope | **Employee** | Сохранить |
| `last_name`, `first_name`, `middle_name` | Биографические | **Person** | Перенести (Phase A/B) |
| `email`, `phone` | Контакты | **Person** | Перенести |
| `telegram_id` | Канал HR-модулей | **Person** (контакт) | Перенос с осторожностью |
| `org_unit_id`, `position_id` | Текущие org/position | **Employment** (projection) | PROJ-EMPLOYMENT |
| `employment_status` | Статус занятости | **Employment** + aggregate status | PROJ-EMPLOYMENT / PROJ-EVENTS |
| `is_manager` | Управленческий признак | **Employment** | PROJ-EMPLOYMENT |
| — | **Отсутствует** | `person_id` | **PROJ-PERSON** |
| — | **Отсутствует** | `employee_code` | PROJ-PERSON / PROJ-EMPLOYMENT |

**Что должно остаться в Employee (target, ADR-050 §3.2):** `id`, `client_id`, `person_id`, `employee_code`, агрегированный статус, read-only индикатор Account.

---

## 3. Dependency Analysis

### 3.1. Целевая цепочка (ADR)

```text
Person
  │ person_id (FK, 1:1 per client — INV-2)
  ▼
Employee  ← Aggregate Root (INV-17)
  │
  ├── Account (0..1) ──► Access / roles     [ADR-049, org-tech]
  ├── Employment[]                         [PROJ-EMPLOYMENT]
  ├── EmployeeConsentRecord
  ├── PtTestAssignment / PtTestSession / PtTelegramBinding
  ├── sa_assessment_sessions / sa_examination_* (skill_assessment)
  └── OrgUnit / Position (as-is flat FK on Employee)
```

### 3.2. As-Is связи (Person отсутствует)

```text
[Identity data on Employee row]
         │
         ▼
    Employee.id  ─────────────────────────────────────────────┐
         │                                                      │
         ├──► Account.employee_id                              │
         ├──► EmployeeConsentRecord.employee_id                 │
         ├──► PtTestAssignment / PtTestSession / PtTelegram*   │
         ├──► sa_* tables (skill_assessment)                   │
         ├──► OrgUnit ◄── Employee.org_unit_id                 │
         ├──► Position ◄── Employee.position_id                │
         └──► Auth: CurrentAccount.client_id ← Employee        │
                                                                │
    HR modules, UI (#employees), Onboarding ◄───────────────────┘
```

### 3.3. Ключевые зависимости

| Тип | Риск при Person |
|-----|-----------------|
| Auth / tenant | Низкий — Employee остаётся |
| HR OS modules (~90 файлов) | Низкий на Phase 1 |
| Telegram binding | Средний |
| Import dedup | Высокий — нужна политика Person dedup (OQ-50-1) |
| `DELETE /api/employees/{id}` | **Критический** — нарушает INV-1, INV-10 |

---

## 4. Gap Analysis

| # | As-Is (2026-06) | Target (ADR-049/050) | Invariant / ADR |
|---|-----------------|----------------------|-----------------|
| 1 | **Нет Person** | Person как identity aggregate | ADR-050 §3.1, INV-1 |
| 2 | **Employee monolith** | Person + Employee разделены | INV-2, §4.3 |
| 3 | **`employee.id` = identity** | Identity = Person | ADR-049 §1.2, INV-15 |
| 4 | **Нет `person_id`** | `Employee.person_id` обязателен | Roadmap PROJ-PERSON |
| 5 | **Нет `employee_code`** | Табельный номер на Employee | ADR-050 §3.2 |
| 6 | **org/position на Employee** | Employment + projection | INV-3, PROJ-EMPLOYMENT |
| 7 | **PATCH lifecycle fields** | Personnel Events only | INV-12 |
| 8 | **`employment_status` flat** | Employment + Archive | INV-9 |
| 9 | **DELETE employee** | No delete; archive logical | INV-1, INV-10 |
| 10 | **Rehire риск** — новый Employee | Same Employee, new Employment | INV-2, INV-4 |
| 11 | **HR modules только `employee_id`** | + optional `person_id` | INV-15 |
| 12 | **Нет Employment, Personal File, Orders** | Полная цепочка ADR-050 | Phase B–C |
| 13 | **Import = source of truth** | HIRE Event + Order | INV-11, P-12 |
| 14 | **Person dedup на Employee** | Person dedup policy | OQ-50-1; политика dedup — в Accepted ADR или дополнительном архитектурном документе при необходимости |

---

## 5. Рекомендуемый план миграции (только этапы)

План согласован с HR Contour Roadmap: `PROJ-PERSON → PROJ-EMPLOYMENT → PROJ-EVENTS`.

### Этап 0 — Архитектурная подготовка

- Assessment (этот документ).
- Перед Этапом 1 убедиться, что физическая модель Person и политика миграции **однозначно следуют из Accepted ADR**. Если нет — может потребоваться дополнительный архитектурный документ (см. [архитектурную оговорку](#архитектурная-оговорка-физическая-модель-и-миграция)). **Это не блокирует Этап 1** («Person без потребителей»), **но блокирует backfill и NOT NULL** на `person_id`.

### Этап 1 — Ввести Person без потребителей

- DDL: таблица `persons` (minimal identity fields).
- Не менять API contracts; не удалять поля с Employee.
- Unit-тесты модели и миграции.

### Этап 2 — Связать Employee с Person (additive)

- `employees.person_id` **NULLABLE** + unique `(client_id, person_id)`.
- Новый Employee → atomic Person + Employee.
- Backfill: 1 Employee → 1 Person (Phase 1 policy).

### Этап 3 — Dual-write / синхронизация

- Write: Person + Employee (transitional).
- Read: пока из Employee.

### Этап 4 — Перевести чтение на Person

- API list/detail/export; `EmployeeSnapshot` в HR bridges.

### Этап 5 — Перевести запись на Person

- PATCH FIO/contacts → Person; `person_id` **NOT NULL**.

### Этап 6 — Удалить устаревшие зависимости (Person scope)

- Drop identity columns с `employees` (после PROJ-EMPLOYMENT plan).

### Последующие проекты

- **PROJ-EMPLOYMENT**, **PROJ-EVENTS**, Phase B+ (Personal File).

```text
Этап 1: Person (unused)
    ↓
Этап 2: Employee.person_id + backfill
    ↓
Этап 3: Dual-write
    ↓
Этап 4: Read from Person
    ↓
Этап 5: Write to Person; person_id NOT NULL
    ↓
Этап 6: Drop legacy columns on Employee
    ↓
PROJ-EMPLOYMENT → PROJ-EVENTS
```

---

## 6. Риски

### 6.1. Риски совместимости

| Риск | Митигация |
|------|-----------|
| API contract drift | Computed fields / stable DTO |
| HR module bridges | Transitional dual fields; `person_id` optional |
| `employee_id` as universal FK | Не менять FK на Phase 1 (INV-15) |
| Platform accounts без Employee | Без изменений (ADR-049 §7.5) |

### 6.2. Риски миграции данных

| Риск | Митигация |
|------|-----------|
| Duplicate persons | Phase 1: 1:1 backfill; dedup — отдельное архитектурное решение, если OQ-50-1 не закрыт ADR-050 |
| Partial backfill | Idempotent job; NOT NULL только после 100% |
| Import re-match | Обновить matching → Person scope |
| Orphan Person (pre-hire) | Допустимо по ADR-050; не в Phase 1 MVP |

### 6.3. Риски API

| Риск | Митигация |
|------|-----------|
| Bulk/import paths | Единый `PersonEmployeeService` |
| Export Excel | Join Person или computed |
| DELETE endpoint | Freeze in PROJ-EVENTS |

### 6.4. Риски UI

| Риск | Митигация |
|------|-----------|
| `static/workspace/index.html` | Phase 4+: API abstraction |
| Status `dismissed` vs Archive | PROJ-TERMINATION |
| Psych / skill assessment UI | Прозрачно через API |

### 6.5. Риски тестов

| Риск | Митигация |
|------|-----------|
| ~14 test files с `/api/employees` | Factory: Person + Employee |
| Psych/skill integration tests | Seed helper с Person |
| Onboarding integration | Update expectations |

---

## 7. План тестирования

### 7.1. Существующие тесты — потребуют изменения

`tests/test_employee_import_excel.py`, `test_employee_list_account_enrichment.py`, `test_employee_pd_consent.py`, `test_admin_roles.py`, `test_auth_mvp.py`, `test_onboarding_integration.py`, `test_org_unit_clone_delete.py`, `test_psychological_testing_api.py`, `test_psych_*` (10+ files), `test_smoke.py`.

### 7.2. Новые тесты (PROJ-PERSON)

`test_person_model_constraints`, `test_person_employee_link`, `test_create_employee_creates_person`, `test_backfill_person_id`, `test_dual_write_consistency`, `test_employee_without_person_rejected`, `test_person_not_deleted_on_employee_archive`.

### 7.3. Обязательные regression tests

1. Auth flow → `CurrentAccount.client_id` unchanged.
2. Account create → valid `employee_id`.
3. GET /api/employees — list/search, response shape.
4. Import Excel — create + update.
5. Onboarding — admin Employee + Account.
6. Psych assignment — by `employee_id`.
7. Telegram binding — resolve by `telegram_id`.
8. Employee delete guard — `employee_has_account`.
9. Multi-tenant isolation — Person scoped by `client_id`.

---

## 8. Оценка сложности

| Область | Phase 1 | Full Phase A |
|---------|---------|--------------|
| DB schema | Low–Medium | Medium |
| Core API | Medium | High |
| HR modules | Low | Medium |
| UI | Low (Phase 1) | Medium–High |
| Data migration | Medium | High |
| Test suite | Medium | High |
| **Итого** | **Medium (3–5 days)** | **High (2–4 sprints)** |

---

## 9. Файлы, затронутые на первом этапе реализации (Этап 1)

| Файл | Изменение |
|------|-----------|
| `app/models.py` | + `class Person` |
| `app/migrate.py` | + `migrate_persons_table()` |
| `tests/test_person_foundation.py` *(new)* | Model + migration tests |

**Вероятно на Этапе 2:** `app/models.py` (`person_id`), `app/migrate.py`, `app/schemas.py`, `app/routers/employees.py`, `app/onboarding.py`, employee/onboarding tests.

**Не затрагиваются на Этапе 1:** UI, HR modules, `app/routers/accounts.py`, публичный API surface.

---

## 10. Открытые вопросы

| # | Вопрос | Owner | Блокирует Phase 1? |
|---|--------|-------|-------------------|
| OQ-P-1 | Физическая модель Person и политика миграции: полностью покрыты Accepted ADR или требуют дополнительного архитектурного документа | Architecture / PROJ-PERSON | **Не блокирует Этап 1; блокирует backfill и NOT NULL** |
| OQ-50-1 | Person dedup: `person_code` vs match по документам | ADR-050 / architecture | Нет для 1:1 backfill |
| OQ-P-2 | Минимальный набор полей Person на Phase 1 | PROJ-PERSON | Scope Этапа 1 |
| OQ-P-3 | Nullable `person_id` — duration & enforcement | PROJ-PERSON | Этап 2 vs 5 |
| OQ-P-4 | Публичный `/api/persons` или internal-only | PROJ-PERSON | Нет |
| OQ-50-8 | Какие PATCH поля Employee допустимы как non-lifecycle | PROJ-EVENTS | Нет для Phase 1 |
| OQ-P-5 | `telegram_id` — Person contact или Employee operational field | PROJ-PERSON / HR OS | Этап 4–5 |
| OQ-P-6 | Legacy `persons` table в dev DB | Ops | Нет |

---

## 11. Соответствие governance

| Требование | Статус |
|------------|--------|
| ARCHITECTURE_GOVERNANCE — решения только в ADR | ✅ |
| ADR-049 — Person → Employee → Account | ✅ Gap зафиксирован |
| ADR-050 §3.1, §4.3, INV-1/2 | ✅ |
| Roadmap PROJ-PERSON → PROJ-EMPLOYMENT | ✅ |
| Код / БД / API / UI не изменялись в assessment | ✅ |

---

## 12. Рекомендуемый следующий шаг

1. **Проверить**, закрывают ли ADR-049/050/051 физическую модель Person и миграцию; при пробелах — **подготовить дополнительный архитектурный документ без привязки к номеру ADR заранее.**
2. **Утвердить scope Этапа 1** — минимальные поля Person.
3. **Начать PROJ-PERSON Этап 1** отдельным PR без изменения API/UI.

---

*Документ подготовлен в рамке PROJ-PERSON Phase A assessment. Реализация не выполнялась.*
