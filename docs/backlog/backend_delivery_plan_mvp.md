# Документ №7. Backend Delivery Plan (MVP)

## 1. Назначение документа

Этот документ переводит проект из уровня архитектуры и backlog в уровень инженерной поставки backend-части.

Если предыдущие артефакты отвечали на вопросы:

- что строим;
- какие сущности есть в системе;
- как выглядит one-click onboarding;
- какие endpoint'ы должны быть в MVP;
- в какой последовательности идут фазы,

то этот документ отвечает на вопрос:

**как именно организовать backend-реализацию, чтобы команда могла начать код без архитектурных разрывов и без повторного перепроектирования по ходу разработки**.

Документ предназначен для:

- backend-разработчиков;
- технического лидера;
- архитектора;
- разработчиков frontend, которым нужен стабильный backend-контур;
- QA, которым нужно понимать последовательность появления контрактов.

---

## 2. Цели backend delivery plan

Backend Delivery Plan должен обеспечить:

1. Понятную декомпозицию backend по модулям.
2. Ясный порядок реализации endpoint'ов.
3. Понятную структуру DTO / schema / service-layer.
4. Отделение CRUD-логики от orchestration-логики.
5. Управляемую последовательность миграций БД.
6. Минимизацию повторных сломов контракта между этапами.
7. Подготовку основы для OpenAPI spec, тестов и CI.

---

## 3. Принципы backend-реализации

### 3.1. Вертикальная поставка, а не только горизонтальные слои

Хотя backend технически состоит из router / service / repository / schema / model, поставка должна идти вертикальными инкрементами:

- сначала один рабочий доменный блок целиком;
- затем следующий;
- затем orchestration.

Это позволяет быстрее проверять результат и уменьшает число зависших полуреализованных модулей.

### 3.2. CRUD отдельно, orchestration отдельно

Критически важно не смешивать:

- простые CRUD-сервисы доменных сущностей;
- многошаговый onboarding orchestration.

Иначе orchestration начнёт напрямую писать в БД, дублировать бизнес-валидацию и ломать повторное использование доменных сервисов.

Правильная модель:

- доменные сервисы умеют работать с одной сущностью или одним доменным блоком;
- orchestration-сервис вызывает доменные сервисы в нужной последовательности;
- orchestration не знает SQL-детали напрямую.

### 3.3. DTO и API contract — отдельный слой

Нужно рано развести:

- transport schemas (request/response);
- внутренние доменные команды;
- ORM / database models.

Это снижает связность и предотвращает ситуации, когда API-контракт случайно становится копией таблицы БД.

### 3.4. Сначала предсказуемость, потом гибкость

Для MVP важнее:

- прозрачные статусы;
- однозначные поля;
- простой словарь ошибок;
- контролируемая идемпотентность,

чем «универсальность на все случаи».

---

## 4. Целевая структура backend-модулей

Ниже приведена рекомендуемая модульная структура backend.

```text
app/
  main.py
  config.py
  db/
    engine.py
    session.py
    base.py
    models/
      client.py
      enterprise_template.py
      role.py
      org_unit.py
      position.py
      employee.py
      account.py
      account_role.py
      onboarding_run.py
      onboarding_run_step.py
      idempotency_key.py
  api/
    deps.py
    errors.py
    router.py
    v1/
      clients.py
      enterprise_templates.py
      roles.py
      org_units.py
      positions.py
      employees.py
      accounts.py
      bootstrap.py
      onboarding_runs.py
  schemas/
    common.py
    clients.py
    enterprise_templates.py
    roles.py
    org_units.py
    positions.py
    employees.py
    accounts.py
    bootstrap.py
    onboarding_runs.py
  services/
    clients_service.py
    enterprise_templates_service.py
    roles_service.py
    org_units_service.py
    positions_service.py
    employees_service.py
    accounts_service.py
    onboarding_validation_service.py
    onboarding_run_service.py
    enterprise_bootstrap_service.py
  repositories/
    clients_repo.py
    enterprise_templates_repo.py
    roles_repo.py
    org_units_repo.py
    positions_repo.py
    employees_repo.py
    accounts_repo.py
    onboarding_runs_repo.py
    idempotency_repo.py
  domain/
    enums.py
    errors.py
    commands.py
    result_types.py
  core/
    security.py
    logging.py
    tracing.py
    idempotency.py
    pagination.py
  tests/
    unit/
    integration/
    e2e/
```

Это не догма, но для MVP такая структура даёт хороший баланс между простотой и расширяемостью.

---

## 5. Разделение ответственности по слоям

## 5.1. API routers

Роутеры должны отвечать только за:

- разбор входного HTTP-запроса;
- привязку request schema;
- вызов соответствующего service;
- возврат response schema;
- трансляцию известных ошибок в HTTP-коды.

Роутеры не должны:

- содержать SQL;
- содержать orchestration-логику;
- делать длинные бизнес-валидации;
- знать детали нескольких таблиц сразу.

## 5.2. Schemas / DTO

Схемы должны содержать:

- request DTO;
- response DTO;
- list envelope;
- error envelope;
- enum-like constraints для transport-уровня.

Важно разделять:

- `ClientCreateRequest`
- `ClientUpdateRequest`
- `ClientResponse`
- `ClientListResponse`

а не использовать одну универсальную схему на всё.

## 5.3. Services

Сервисный слой — основной носитель бизнес-логики.

Он должен отвечать за:

- валидации доменного уровня;
- orchestration вызовов репозиториев;
- нормализацию входных данных;
- реализацию правил уникальности и связности;
- возврат понятного доменного результата.

## 5.4. Repositories

Репозиторный слой отвечает за:

- чтение и запись в БД;
- изоляцию ORM/SQL деталей;
- простые селекты и апдейты;
- отсутствие бизнес-логики за пределами необходимых query constraints.

## 5.5. Domain layer

Слой `domain` нужен, чтобы вынести:

- enum'ы статусов;
- коды ошибок;
- доменные типы;
- команды / result objects,

и не размазывать эти определения по router/service/model слоям.

---

## 6. Модули MVP и их порядок поставки

Рекомендуемый порядок backend delivery:

1. Core foundation
2. Roles + Enterprise Templates + Clients
3. Org Units
4. Positions
5. Employees
6. Accounts + Account Roles
7. Onboarding Runs
8. Bootstrap Orchestration
9. Hardening + tests + OpenAPI cleanup

Это именно порядок реализации, а не логическая карта сущностей.

---

# 7. Delivery Wave 1 — Core Foundation

## 7.1. Цель

Подготовить каркас backend, на который будут навешиваться все доменные модули.

## 7.2. Что реализовать

### Infra / Core

- конфигурация приложения;
- подключение к БД;
- session / transaction management;
- базовый API router `/api/v1`;
- health endpoint;
- error handling middleware / handlers;
- request_id / trace_id support;
- базовые list/pagination helpers;
- единый JSON error envelope.

### Domain / Shared

- базовые enum'ы статусов;
- общие exception classes;
- `NotFound`, `ValidationError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`;
- общий response envelope для list endpoints.

### Testing foundation

- тестовая БД / test session setup;
- базовый integration test harness;
- фикстуры для seed roles/templates.

## 7.3. Результат

После этой волны backend готов к последовательному наращиванию доменных маршрутов без хаотического копирования инфраструктурного кода.

---

# 8. Delivery Wave 2 — Roles, Enterprise Templates, Clients

## 8.1. Цель

Реализовать первый законченный доменный контур: справочник ролей, шаблоны предприятий и заказчики.

## 8.2. Таблицы / модели

### `roles`
Минимальные поля:
- id
- code
- name
- is_active
- created_at
- updated_at

### `enterprise_templates`
Минимальные поля:
- id
- code
- name
- version
- description
- is_active
- created_at
- updated_at

### `enterprise_template_org_units`
Минимальные поля:
- id
- template_id
- code
- name
- parent_code
- unit_type
- sort_order

### `enterprise_template_positions`
Минимальные поля:
- id
- template_id
- code
- name
- org_unit_code
- sort_order

### `clients`
Минимальные поля:
- id
- code
- name
- bin
- status
- template_id
- created_at
- updated_at

## 8.3. Роутеры

- `GET /api/v1/roles`
- `GET /api/v1/enterprise-templates`
- `GET /api/v1/enterprise-templates/{template_id}`
- `GET /api/v1/enterprise-templates/{template_id}/structure-preview`
- `GET /api/v1/clients`
- `POST /api/v1/clients`
- `GET /api/v1/clients/{client_id}`
- `PATCH /api/v1/clients/{client_id}`

## 8.4. Сервисы

### `RolesService`
Функции:
- list_roles

### `EnterpriseTemplatesService`
Функции:
- list_templates
- get_template
- get_structure_preview

### `ClientsService`
Функции:
- list_clients
- create_client
- get_client
- update_client
- validate_client_code_uniqueness
- validate_template_reference

## 8.5. DTO / schemas

Нужны схемы:

- `RoleResponse`
- `RoleListResponse`
- `EnterpriseTemplateResponse`
- `EnterpriseTemplateListResponse`
- `TemplateStructurePreviewResponse`
- `ClientCreateRequest`
- `ClientUpdateRequest`
- `ClientResponse`
- `ClientListResponse`

## 8.6. Acceptance criteria

1. Список ролей стабилен и seed'ится автоматически.
2. Шаблоны читаются через API.
3. Preview шаблона доступен отдельным endpoint'ом.
4. Заказчика можно создать и изменить.
5. Дубли по `client.code` блокируются.
6. Невалидный `template_id` блокируется как бизнес-ошибка.

---

# 9. Delivery Wave 3 — Org Units

## 9.1. Цель

Сделать отдельный устойчивый модуль оргструктуры, на который затем будут опираться должности, сотрудники и onboarding.

## 9.2. Таблица / модель `org_units`

Минимальные поля:

- id
- client_id
- code
- name
- parent_id
- unit_type
- is_active
- sort_order
- created_at
- updated_at

## 9.3. Роутеры

- `GET /api/v1/org-units`
- `GET /api/v1/org-units/tree`
- `POST /api/v1/org-units`
- `PATCH /api/v1/org-units/{org_unit_id}`
- `POST /api/v1/org-units/bulk`

## 9.4. Сервис `OrgUnitsService`

Функции:

- list_org_units
- get_org_tree
- create_org_unit
- update_org_unit
- bulk_create_org_units
- validate_parent_reference
- validate_org_unit_code_uniqueness
- validate_no_cycles

## 9.5. Репозиторий `OrgUnitsRepo`

Функции:

- get_by_id
- list_by_client
- list_children
- exists_by_code
- create
- update
- bulk_insert
- fetch_tree_source

## 9.6. DTO / schemas

- `OrgUnitCreateRequest`
- `OrgUnitUpdateRequest`
- `OrgUnitResponse`
- `OrgUnitListResponse`
- `OrgUnitTreeNodeResponse`
- `OrgUnitBulkCreateRequest`
- `OrgUnitBulkCreateResult`

## 9.7. Архитектурное замечание

Tree endpoint лучше строить либо:

- в service-слое из flat списка,

либо:

- на основе materialized representation, если позже это понадобится.

Для MVP достаточно строить дерево в service-слое.

## 9.8. Acceptance criteria

1. В пределах одного клиента код оргединицы уникален.
2. Нельзя создать цикл через `parent_id`.
3. Можно получить дерево оргструктуры одним запросом.
4. Bulk create поддерживает создание структуры из массива.

---

# 10. Delivery Wave 4 — Positions

## 10.1. Цель

Добавить штатные позиции поверх уже готовой оргструктуры.

## 10.2. Таблица / модель `positions`

Минимальные поля:

- id
- client_id
- org_unit_id
- code
- name
- grade
- is_active
- created_at
- updated_at

## 10.3. Роутеры

- `GET /api/v1/positions`
- `POST /api/v1/positions`
- `PATCH /api/v1/positions/{position_id}`
- `POST /api/v1/positions/bulk`

## 10.4. Сервис `PositionsService`

Функции:

- list_positions
- create_position
- update_position
- bulk_create_positions
- validate_org_unit_reference
- validate_position_code_uniqueness

## 10.5. DTO / schemas

- `PositionCreateRequest`
- `PositionUpdateRequest`
- `PositionResponse`
- `PositionListResponse`
- `PositionBulkCreateRequest`
- `PositionBulkCreateResult`

## 10.6. Acceptance criteria

1. Должность не может ссылаться на несуществующее подразделение.
2. Можно создавать должности через единичный и bulk endpoint.
3. Список должностей фильтруется по клиенту и подразделению.

---

# 11. Delivery Wave 5 — Employees

## 11.1. Цель

Добавить кадровый контур предприятия.

## 11.2. Таблица / модель `employees`

Минимальные поля:

- id
- client_id
- last_name
- first_name
- middle_name
- email
- phone
- org_unit_id
- position_id
- employment_status
- is_manager
- created_at
- updated_at

## 11.3. Роутеры

- `GET /api/v1/employees`
- `POST /api/v1/employees`
- `GET /api/v1/employees/{employee_id}`
- `PATCH /api/v1/employees/{employee_id}`
- `POST /api/v1/employees/bulk`

## 11.4. Сервис `EmployeesService`

Функции:

- list_employees
- create_employee
- get_employee
- update_employee
- bulk_create_employees
- validate_org_unit_reference
- validate_position_reference
- validate_employee_identity_rules

## 11.5. DTO / schemas

- `EmployeeCreateRequest`
- `EmployeeUpdateRequest`
- `EmployeeResponse`
- `EmployeeListResponse`
- `EmployeeBulkCreateRequest`
- `EmployeeBulkCreateResult`

## 11.6. Важное решение MVP

Для MVP не нужно строить сложную кадровую историю. Достаточно текущего состояния сотрудника.

Не включать пока:

- историю переводов;
- совместительства;
- ставки;
- многоаккаунтность;
- сложный employee lifecycle.

## 11.7. Acceptance criteria

1. Сотрудника можно привязать к подразделению и должности.
2. Невалидные ссылки блокируются.
3. Если создаётся сотрудник для будущего аккаунта, email проходит базовую валидацию.
4. Bulk create позволяет загрузить стартовый список сотрудников.

---

# 12. Delivery Wave 6 — Accounts and Account Roles

## 12.1. Цель

Подготовить access-ready слой для последующего автоматического создания пользователей при onboarding.

## 12.2. Таблицы / модели

### `accounts`
- id
- employee_id
- login
- password_hash
- status
- created_at
- updated_at

### `account_roles`
- id
- account_id
- role_id
- assigned_at

## 12.3. Роутеры

- `GET /api/v1/accounts`
- `POST /api/v1/accounts`
- `PATCH /api/v1/accounts/{account_id}`
- `POST /api/v1/accounts/bulk`
- опционально `POST /api/v1/accounts/{account_id}/reset-password`

## 12.4. Сервис `AccountsService`

Функции:

- list_accounts
- create_account
- update_account
- bulk_create_accounts
- assign_roles
- replace_roles
- validate_employee_reference
- validate_login_uniqueness
- validate_role_codes

## 12.5. DTO / schemas

- `AccountCreateRequest`
- `AccountUpdateRequest`
- `AccountResponse`
- `AccountListResponse`
- `AccountBulkCreateRequest`
- `AccountBulkCreateResult`
- `ResetPasswordRequest` или action schema

## 12.6. Важное решение MVP

Нужно рано зафиксировать:

- login = email или допускается отдельный login;
- один сотрудник = один аккаунт в MVP;
- набор ролей может быть множественным, но из ограниченного словаря.

## 12.7. Acceptance criteria

1. Аккаунт нельзя создать без существующего сотрудника.
2. Логин уникален.
3. Роли можно назначить по `role_codes`.
4. Аккаунты читаются через список по клиенту.
5. Bulk create готов для bootstrap-сценария.

---

# 13. Delivery Wave 7 — Onboarding Runs

## 13.1. Цель

Подготовить инфраструктуру наблюдаемого orchestration до того, как будет написан сам bootstrap flow.

## 13.2. Таблицы / модели

### `onboarding_runs`
- id
- request_id
- client_id
- status
- current_step
- progress
- payload_hash
- started_at
- finished_at
- error_message
- created_at

### `onboarding_run_steps`
- id
- run_id
- step_code
- status
- started_at
- finished_at
- error_message
- payload_snapshot

### `idempotency_keys` или эквивалент
- id
- key
- payload_hash
- scope
- resource_type
- resource_id
- created_at

## 13.3. Роутеры

- `GET /api/v1/onboarding-runs`
- `GET /api/v1/onboarding-runs/{run_id}`
- `GET /api/v1/onboarding-runs/{run_id}/steps`

## 13.4. Сервис `OnboardingRunService`

Функции:

- create_run
- mark_run_running
- mark_step_running
- mark_step_done
- mark_step_failed
- mark_run_completed
- mark_run_failed
- mark_run_partially_completed
- list_runs
- get_run
- get_run_steps

## 13.5. Зачем делать это до bootstrap

Потому что сам bootstrap лучше писать уже на готовую модель наблюдения. Тогда orchestration сразу будет прозрачен, а не «дописан потом».

## 13.6. Acceptance criteria

1. Модель run и step существует независимо от реализации bootstrap.
2. Статусы и шаги читаются через API.
3. Инфраструктура run-ready для интеграции с orchestration.

---

# 14. Delivery Wave 8 — Bootstrap Orchestration

## 14.1. Цель

Реализовать главный value-flow MVP: one-click onboarding предприятия.

## 14.2. Роутер

- `POST /api/v1/bootstrap/enterprise`

## 14.3. Основные сервисы

### `OnboardingValidationService`
Функции:
- validate_payload_structure
- validate_template_reference
- validate_internal_codes_uniqueness
- validate_cross_references
- validate_account_creation_preconditions

### `EnterpriseBootstrapService`
Функции:
- bootstrap_enterprise
- execute_step_create_or_get_client
- execute_step_create_org_units
- execute_step_create_positions
- execute_step_create_employees
- execute_step_create_accounts
- execute_step_assign_roles
- finalize_success
- finalize_failure

### `IdempotencyService`
Функции:
- register_or_get_existing
- compare_payload_hash
- resolve_existing_run
- store_result_reference

## 14.4. Рекомендуемый flow внутри bootstrap

1. Проверка `Idempotency-Key` / `request_id`.
2. Создание `onboarding_run` со статусом `queued`.
3. Полная валидация payload.
4. Если `dry_run=true`, вернуть validation result и не продолжать.
5. Перевести run в `running`.
6. Выполнить шаг `create_or_get_client`.
7. Выполнить шаг `create_org_units`.
8. Выполнить шаг `create_positions`.
9. Выполнить шаг `create_employees`.
10. Выполнить шаг `create_accounts`.
11. Выполнить шаг `assign_roles`.
12. Зафиксировать итоговый статус.

## 14.5. Критическое правило реализации

Bootstrap должен вызывать доменные сервисы, а не писать напрямую в репозитории всех сущностей.

То есть:

- `EnterpriseBootstrapService` вызывает `ClientsService`, `OrgUnitsService`, `PositionsService`, `EmployeesService`, `AccountsService`;
- orchestration управляет последовательностью;
- доменные сервисы управляют логикой создания сущностей.

## 14.6. Dry-run model

Для `dry_run=true` желательно возвращать:

- список ошибок;
- summary по числу сущностей к созданию;
- список предупреждений;
- признак `status=validated`.

## 14.7. Failure model

Для MVP рекомендуется модель:

- partial completion;
- прозрачный status;
- фиксированные шаги и step-level error.

Полный rollback не является обязательным требованием MVP.

## 14.8. Acceptance criteria

1. Один payload создаёт предприятие end-to-end.
2. Повтор identical request не создаёт дублей.
3. Повтор с тем же ключом, но иным payload даёт конфликт.
4. Dry-run не пишет данные в БД.
5. При ошибке run и step фиксируются прозрачно.
6. После успеха run имеет статус `completed`.

---

# 15. Delivery Wave 9 — Hardening and Contract Stabilization

## 15.1. Цель

Стабилизировать backend до состояния, пригодного для реального UI wizard и демонстрации MVP.

## 15.2. Что входит

### Contract hardening
- финализация response schemas;
- финализация error codes;
- консистентность пагинации;
- унификация filter/query params.

### Observability
- enriched logs;
- trace_id в ошибках;
- run-level logging;
- step-level diagnostics.

### Testing
- integration tests для clients/templates;
- integration tests для org/positions/employees/accounts;
- e2e тест bootstrap happy path;
- тест dry-run;
- тест idempotency;
- тест частичного сбоя.

### OpenAPI work
- генерация или ручная сборка OpenAPI spec;
- выверка примеров запросов/ответов;
- синхронизация с frontend.

## 15.3. Acceptance criteria

1. Контракт стабилен и не требует ручной адаптации во frontend.
2. Основные happy path и failure path покрыты тестами.
3. OpenAPI отражает фактическое поведение backend.
4. Bootstrap можно безопасно демонстрировать и тестировать повторно.

---

## 16. Порядок миграций БД

Рекомендуемая последовательность миграций:

1. baseline core tables
   - roles
   - enterprise_templates
   - enterprise_template_org_units
   - enterprise_template_positions
   - clients

2. org structure tables
   - org_units

3. workforce tables
   - positions
   - employees

4. access tables
   - accounts
   - account_roles

5. orchestration tables
   - onboarding_runs
   - onboarding_run_steps
   - idempotency_keys

Такой порядок минимизирует циклические зависимости и упрощает rollout.

---

## 17. Порядок коммитов и delivery increments

Ниже — практический рекомендуемый порядок коммитов.

### Increment 1
- app skeleton
- db base
- config
- common errors
- api v1 root

### Increment 2
- roles models + seed + endpoint
- templates models + endpoints
- clients model + CRUD endpoints

### Increment 3
- org_units model + CRUD + tree + tests

### Increment 4
- positions model + CRUD + tests

### Increment 5
- employees model + CRUD + tests

### Increment 6
- accounts + account_roles + CRUD + tests

### Increment 7
- onboarding_runs + onboarding_run_steps + run endpoints

### Increment 8
- bootstrap validation + orchestration + dry-run + idempotency

### Increment 9
- contract stabilization
- logging hardening
- OpenAPI spec
- final integration tests

Это позволяет держать историю Git в понятном и восстанавливаемом виде.

---

## 18. Матрица backend deliverables

| Wave | Основной результат | Ключевые модули |
|---|---|---|
| 1 | Каркас backend | core, db, api shared |
| 2 | Клиенты и шаблоны | clients, enterprise_templates, roles |
| 3 | Оргструктура | org_units |
| 4 | Должности | positions |
| 5 | Сотрудники | employees |
| 6 | Аккаунты и роли доступа | accounts, account_roles |
| 7 | Наблюдаемость запусков | onboarding_runs |
| 8 | One-click onboarding | bootstrap, validation, idempotency |
| 9 | Stabilization | tests, logging, OpenAPI |

---

## 19. Минимальный пакет тестов по волнам

### Wave 2
- create client
- duplicate client code
- get template preview

### Wave 3
- create org unit
- invalid parent
- tree retrieval
- cycle prevention

### Wave 4
- create position
- invalid org_unit reference

### Wave 5
- create employee
- invalid position reference
- employee list filters

### Wave 6
- create account
- duplicate login
- invalid role assignment

### Wave 7
- create and read onboarding run
- create and read steps

### Wave 8
- bootstrap happy path
- bootstrap dry-run
- bootstrap idempotent retry
- bootstrap conflicting retry
- bootstrap partial failure

---

## 20. Ключевые инженерные решения, которые нужно принять заранее

До начала активной реализации нужно явно зафиксировать:

1. **Тип идентификаторов** — UUID или integer.
2. **Login policy** — login всегда равен email или нет.
3. **Политика уникальности кодов**:
   - client code;
   - org unit code;
   - position code.
4. **Failure model bootstrap**:
   - partial completion recommended.
5. **Транзакционная стратегия**:
   - одна большая транзакция или шаговые транзакции.
6. **Seed policy**:
   - как поставляются шаблоны и роли.
7. **OpenAPI source of truth**:
   - code-first или spec-first.

Для MVP рекомендуется:

- UUID или integer — любой один стандарт без смешения;
- login = email;
- partial completion;
- step-level transactions;
- roles/templates через seed;
- OpenAPI code-first с последующей фиксацией spec.

---

## 21. Что не нужно усложнять в backend MVP

Не следует преждевременно добавлять:

- generic workflow engine;
- event bus для всех внутренних действий;
- сложный policy engine;
- DDD в избыточно тяжёлой форме;
- CQRS/event sourcing;
- полноценный IAM;
- универсальный template editor;
- поддержку всех внешних источников данных.

MVP backend должен быть не «идеально абстрактным», а надёжно исполнимым.

---

## 22. Итог

Backend Delivery Plan задаёт для проекта инженерную траекторию реализации MVP backend-части.

Он фиксирует:

- модульную структуру;
- роли слоёв;
- последовательность delivery waves;
- порядок миграций;
- порядок коммитов;
- состав сервисов и роутеров;
- место orchestration в общей архитектуре.

После этого документа команда уже может переходить к:

- постановке backend-задач по wave'ам;
- созданию миграций;
- реализации router/service/repository модулей;
- синхронизации frontend с реальными контрактами.

---

## 23. Следующий логичный документ

После Backend Delivery Plan наиболее полезны два следующих артефакта:

### Вариант A — Permission Matrix MVP
Чтобы зафиксировать, кто именно может:
- запускать onboarding;
- создавать клиентов;
- редактировать оргструктуру;
- создавать аккаунты;
- просматривать run status.

### Вариант B — Frontend Delivery Plan
Чтобы зеркально разложить:
- экраны;
- wizard steps;
- формы;
- UX-состояния;
- интеграцию с backend contracts.

Если цель — как можно быстрее двигаться к рабочему продукту, после этого документа особенно полезно сделать **Frontend Delivery Plan**.

