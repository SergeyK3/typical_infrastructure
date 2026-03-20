# Документ №5. OpenAPI Baseline v1

## 1. Назначение документа

Этот документ фиксирует минимальный API-контур для MVP системы типовой инфраструктуры проектов в части one-click onboarding предприятия.

Цель документа — определить стартовый набор endpoint'ов, достаточный для:

- создания и ведения заказчиков;
- использования шаблонов типовых предприятий;
- построения оргструктуры;
- заведения должностей;
- заведения сотрудников;
- создания аккаунтов и назначения ролей;
- запуска сценария bootstrap / onboarding;
- отслеживания статуса выполнения onboarding run.

Документ не претендует на полный production-ready OpenAPI 3.1 specification. Это baseline-уровень, который:

- фиксирует границы MVP;
- задаёт единый язык между business, backend и frontend;
- служит основой для дальнейшей детализации OpenAPI spec, backend routes и MVP backlog.

---

## 2. Роль OpenAPI Baseline v1 в общем пакете артефактов

Данный документ является связующим слоем между уже подготовленными материалами:

- резюме идеи;
- черновым ТЗ;
- архитектурной концепцией;
- концептуальной моделью данных / ERD;
- мастер-сценарием создания предприятия — one-click onboarding.

Если ERD отвечает на вопрос **какие сущности и связи существуют**, а мастер-сценарий — **как пользователь и система проходят onboarding-поток**, то OpenAPI Baseline v1 отвечает на вопрос:

**через какие API-контракты это будет реализовано в MVP**.

---

## 3. Принципы baseline-контракта

### 3.1. Что входит в baseline

В baseline включаются только те endpoints, без которых невозможен минимальный рабочий контур onboarding:

1. Заказчики.
2. Шаблоны предприятий.
3. Оргструктура.
4. Должности.
5. Сотрудники.
6. Аккаунты и роли.
7. Bootstrap / onboarding run.
8. Статусы deployment / onboarding run.

### 3.2. Что сознательно не включается в baseline v1

В baseline v1 не детализируются:

- аудит изменений;
- массовый импорт из внешних HR-систем;
- сложные поисковые и фильтрационные API;
- тонкая RBAC-матрица;
- уведомления;
- интеграции с LMS, KPI, assessment-провайдерами;
- версионирование шаблонов на production-уровне;
- webhooks;
- soft delete / архивирование во всех деталях.

Эти аспекты могут появиться в следующих версиях контракта.

### 3.3. Базовые требования к API

Для всех endpoint'ов baseline предполагаются следующие правила:

- формат обмена: JSON;
- кодировка: UTF-8;
- аутентификация: Bearer token;
- базовый префикс: `/api/v1`;
- время в ответах: ISO 8601;
- идентификаторы сущностей: UUID или numeric ID — допустимы оба варианта, но в пределах MVP должен быть выбран один стандарт;
- destructive-операции в baseline по возможности заменяются флагом `is_active=false`.

---

## 4. Общая структура API

Предлагаемый базовый префикс:

`/api/v1`

Группы endpoint'ов:

- `/clients`
- `/enterprise-templates`
- `/org-units`
- `/positions`
- `/employees`
- `/accounts`
- `/roles`
- `/onboarding-runs`

Дополнительно допустим служебный orchestration endpoint:

- `/bootstrap/enterprise`

Health / readiness (Step 7):

- `GET /health/ready` — readiness probe для deployment

---

## 5. Сквозные соглашения

## 5.1. Общая форма успешного ответа

Для list endpoints:

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

Для single resource endpoints:

```json
{
  "id": "...",
  "status": "active",
  "created_at": "2026-03-11T10:00:00Z",
  "updated_at": "2026-03-11T10:00:00Z"
}
```

Для orchestration / run endpoints:

```json
{
  "run_id": "...",
  "status": "queued",
  "started_at": null,
  "finished_at": null
}
```

## 5.2. Общая форма ошибки

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "details": [
      {
        "field": "client_name",
        "issue": "required"
      }
    ],
    "trace_id": "..."
  }
}
```

## 5.3. Рекомендуемые коды ответа

- `200 OK` — успешное чтение или обновление;
- `201 Created` — сущность создана;
- `202 Accepted` — запуск orchestration принят в обработку;
- `400 Bad Request` — некорректный запрос;
- `401 Unauthorized` — отсутствует или невалиден токен;
- `403 Forbidden` — недостаточно прав;
- `404 Not Found` — сущность не найдена;
- `409 Conflict` — конфликт состояния или нарушение идемпотентности;
- `422 Unprocessable Entity` — бизнес-валидация не пройдена;
- `500 Internal Server Error` — непредвиденная ошибка.

## 5.4. Идемпотентность

Для операций запуска bootstrap / onboarding желательно поддержать:

- заголовок `Idempotency-Key`;
- либо явное поле `request_id` в body.

Если один и тот же запрос отправлен повторно, backend должен:

- вернуть уже существующий `run_id`, если запуск идентичен;
- вернуть `409 Conflict`, если request_id совпал, но payload отличается;
- не создавать дубли заказчика, оргструктуры, сотрудников и аккаунтов.

---

## 6. Раздел: Заказчики

## 6.1. Назначение

API заказчиков управляет юридическими лицами, для которых в дальнейшем разворачивается типовая инфраструктура предприятия.

## 6.2. Минимальная модель ресурса

```json
{
  "id": "client_001",
  "code": "TOO_ALFA",
  "name": "ТОО Альфа",
  "bin": "123456789012",
  "status": "active",
  "template_id": "tmpl_default_b2b",
  "created_at": "2026-03-11T10:00:00Z",
  "updated_at": "2026-03-11T10:00:00Z"
}
```

## 6.3. Endpoint'ы

### `GET /api/v1/clients`

Назначение: получить список заказчиков.

Параметры:

- `limit`
- `offset`
- `status`
- `search`

Ответ `200 OK`:

```json
{
  "items": [
    {
      "id": "client_001",
      "code": "TOO_ALFA",
      "name": "ТОО Альфа",
      "status": "active"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `POST /api/v1/clients`

Назначение: создать заказчика вручную вне полного onboarding-потока.

Body:

```json
{
  "code": "TOO_ALFA",
  "name": "ТОО Альфа",
  "bin": "123456789012",
  "template_id": "tmpl_default_b2b"
}
```

Ответ `201 Created`.

### `GET /api/v1/clients/{client_id}`

Назначение: получить карточку заказчика.

### `PATCH /api/v1/clients/{client_id}`

Назначение: обновить основные атрибуты заказчика.

Изменяемые поля MVP:

- `name`
- `status`
- `template_id`

---

## 7. Раздел: Шаблоны предприятий

## 7.1. Назначение

Шаблон предприятия определяет типовую заготовку:

- стандартный набор подразделений;
- допустимые секции;
- типовые должности;
- стандартные роли;
- рекомендуемую структуру первого запуска.

## 7.2. Минимальная модель ресурса

```json
{
  "id": "tmpl_default_b2b",
  "code": "default_b2b",
  "name": "Типовой B2B шаблон",
  "version": "1.0",
  "is_active": true,
  "description": "Базовая структура для корпоративного клиента"
}
```

## 7.3. Endpoint'ы

### `GET /api/v1/enterprise-templates`

Назначение: получить список шаблонов.

### `GET /api/v1/enterprise-templates/{template_id}`

Назначение: получить шаблон и его метаданные.

### `GET /api/v1/enterprise-templates/{template_id}/structure-preview`

Назначение: получить предпросмотр структуры шаблона до запуска onboarding.

Пример ответа:

```json
{
  "template_id": "tmpl_default_b2b",
  "org_units": [
    { "code": "ADMIN", "name": "Администрация" },
    { "code": "HR", "name": "Отдел кадров" },
    { "code": "FIN", "name": "Бухгалтерия" },
    { "code": "PROD", "name": "Производственный отдел" }
  ],
  "positions": [
    { "code": "CEO", "name": "Директор" },
    { "code": "HR_HEAD", "name": "Руководитель отдела кадров" }
  ]
}
```

Примечание: в MVP создание и редактирование шаблонов через API можно не включать, если шаблоны заводятся администратором через seed / backoffice.

---

## 8. Раздел: Оргструктура

## 8.1. Назначение

API оргструктуры управляет подразделениями, секциями и иерархией внутри конкретного заказчика.

## 8.2. Минимальная модель ресурса

```json
{
  "id": "ou_001",
  "client_id": "client_001",
  "code": "HR",
  "name": "Отдел кадров",
  "parent_id": null,
  "unit_type": "department",
  "is_active": true
}
```

## 8.3. Endpoint'ы

### `GET /api/v1/org-units`

Назначение: получить список узлов оргструктуры.

Фильтры:

- `client_id` — обязательно для MVP;
- `parent_id` — опционально;
- `unit_type` — опционально.

### `GET /api/v1/org-units/tree?client_id={client_id}`

Назначение: получить дерево оргструктуры клиента.

### `POST /api/v1/org-units`

Назначение: создать подразделение или секцию.

Body:

```json
{
  "client_id": "client_001",
  "code": "HR",
  "name": "Отдел кадров",
  "parent_id": null,
  "unit_type": "department"
}
```

### `PATCH /api/v1/org-units/{org_unit_id}`

Назначение: обновить подразделение.

### `POST /api/v1/org-units/bulk`

Назначение: массово создать оргединицы в рамках onboarding.

Пример body:

```json
{
  "client_id": "client_001",
  "items": [
    {
      "code": "ADMIN",
      "name": "Администрация",
      "parent_code": null,
      "unit_type": "department"
    },
    {
      "code": "HR",
      "name": "Отдел кадров",
      "parent_code": null,
      "unit_type": "department"
    }
  ]
}
```

---

## 9. Раздел: Должности

## 9.1. Назначение

API должностей описывает штатные роли внутри подразделений клиента.

## 9.2. Минимальная модель ресурса

```json
{
  "id": "pos_001",
  "client_id": "client_001",
  "org_unit_id": "ou_001",
  "code": "HR_HEAD",
  "name": "Руководитель отдела кадров",
  "grade": null,
  "is_active": true
}
```

## 9.3. Endpoint'ы

### `GET /api/v1/positions?client_id={client_id}`

Назначение: получить список должностей клиента.

Фильтры:

- `org_unit_id`
- `search`
- `is_active`

### `POST /api/v1/positions`

Назначение: создать должность.

### `PATCH /api/v1/positions/{position_id}`

Назначение: обновить должность.

### `POST /api/v1/positions/bulk`

Назначение: массово создать должности при onboarding.

---

## 10. Раздел: Сотрудники

## 10.1. Назначение

API сотрудников управляет персональными карточками сотрудников заказчика и их привязкой к должностям / подразделениям.

## 10.2. Минимальная модель ресурса

```json
{
  "id": "emp_001",
  "client_id": "client_001",
  "last_name": "Иванов",
  "first_name": "Иван",
  "middle_name": "Иванович",
  "email": "ivanov@example.com",
  "phone": "+77010000000",
  "org_unit_id": "ou_001",
  "position_id": "pos_001",
  "employment_status": "active",
  "is_manager": true
}
```

## 10.3. Endpoint'ы

### `GET /api/v1/employees?client_id={client_id}`

Назначение: список сотрудников клиента.

Фильтры:

- `org_unit_id`
- `position_id`
- `employment_status`
- `search`

### `POST /api/v1/employees`

Назначение: создать сотрудника.

### `GET /api/v1/employees/{employee_id}`

Назначение: карточка сотрудника.

### `PATCH /api/v1/employees/{employee_id}`

Назначение: обновить карточку сотрудника.

### `POST /api/v1/employees/bulk`

Назначение: массовое создание сотрудников в рамках onboarding.

Пример body:

```json
{
  "client_id": "client_001",
  "items": [
    {
      "last_name": "Иванов",
      "first_name": "Иван",
      "email": "ivanov@example.com",
      "org_unit_code": "HR",
      "position_code": "HR_HEAD",
      "is_manager": true
    }
  ]
}
```

---

## 11. Раздел: Аккаунты и роли

## 11.1. Назначение

Этот блок отвечает за доступ сотрудника в систему:

- создание учётной записи;
- назначение одной или нескольких ролей;
- привязку аккаунта к сотруднику.

## 11.2. Минимальная модель аккаунта

```json
{
  "id": "acc_001",
  "employee_id": "emp_001",
  "login": "ivanov@example.com",
  "status": "active",
  "roles": [
    {
      "code": "CLIENT_ADMIN",
      "name": "Администратор заказчика"
    }
  ]
}
```

## 11.3. Endpoint'ы ролей

### `GET /api/v1/roles`

Назначение: получить справочник ролей, доступных в MVP.

Пример ответа:

```json
{
  "items": [
    { "code": "CLIENT_OWNER", "name": "Владелец клиента" },
    { "code": "CLIENT_ADMIN", "name": "Администратор заказчика" },
    { "code": "HR_MANAGER", "name": "HR-менеджер" },
    { "code": "DEPARTMENT_HEAD", "name": "Руководитель подразделения" },
    { "code": "EMPLOYEE", "name": "Сотрудник" }
  ],
  "total": 5,
  "limit": 50,
  "offset": 0
}
```

## 11.4. Endpoint'ы аккаунтов

### `GET /api/v1/accounts?client_id={client_id}`

Назначение: список аккаунтов клиента.

### `POST /api/v1/accounts`

Назначение: создать аккаунт для сотрудника.

Body:

```json
{
  "employee_id": "emp_001",
  "login": "ivanov@example.com",
  "temporary_password": "TempPass123!",
  "role_codes": ["CLIENT_ADMIN"]
}
```

### `PATCH /api/v1/accounts/{account_id}`

Назначение: обновить статус аккаунта или набор ролей.

### `POST /api/v1/accounts/bulk`

Назначение: массовое создание аккаунтов в рамках onboarding.

### `POST /api/v1/accounts/{account_id}/reset-password`

Назначение: инициировать сброс пароля.

Примечание: endpoint может быть включён в MVP только при наличии минимального auth-контура. Если auth ещё не реализуется, его можно перенести в Phase 2.

---

## 12. Раздел: Bootstrap / One-click onboarding

## 12.1. Назначение

Это главный orchestration-слой MVP. Он принимает мастер-запрос и запускает пошаговое создание предприятия:

1. создаёт заказчика;
2. фиксирует выбранный шаблон;
3. создаёт оргструктуру;
4. создаёт должности;
5. создаёт сотрудников;
6. создаёт аккаунты;
7. назначает базовые роли;
8. возвращает статус выполнения сценария.

## 12.2. Основной endpoint orchestration

### `POST /api/v1/bootstrap/enterprise`

Назначение: запустить one-click onboarding предприятия.

Заголовки:

- `Authorization: Bearer <token>`
- `Idempotency-Key: <uuid>`

Body:

```json
{
  "request_id": "req_20260311_001",
  "client": {
    "code": "TOO_ALFA",
    "name": "ТОО Альфа",
    "bin": "123456789012"
  },
  "template_id": "tmpl_default_b2b",
  "org_units": [
    {
      "code": "ADMIN",
      "name": "Администрация",
      "parent_code": null,
      "unit_type": "department"
    },
    {
      "code": "HR",
      "name": "Отдел кадров",
      "parent_code": null,
      "unit_type": "department"
    }
  ],
  "positions": [
    {
      "code": "CEO",
      "name": "Директор",
      "org_unit_code": "ADMIN"
    },
    {
      "code": "HR_HEAD",
      "name": "Руководитель отдела кадров",
      "org_unit_code": "HR"
    }
  ],
  "employees": [
    {
      "external_key": "emp_1",
      "last_name": "Иванов",
      "first_name": "Иван",
      "email": "ivanov@example.com",
      "org_unit_code": "ADMIN",
      "position_code": "CEO",
      "role_codes": ["CLIENT_OWNER"]
    },
    {
      "external_key": "emp_2",
      "last_name": "Петрова",
      "first_name": "Анна",
      "email": "petrova@example.com",
      "org_unit_code": "HR",
      "position_code": "HR_HEAD",
      "role_codes": ["HR_MANAGER"]
    }
  ],
  "options": {
    "create_accounts": true,
    "send_invites": false,
    "dry_run": false
  }
}
```

### Ответ `202 Accepted`

```json
{
  "run_id": "run_001",
  "status": "queued",
  "request_id": "req_20260311_001",
  "client_code": "TOO_ALFA"
}
```

## 12.3. Поведение dry-run

Если `options.dry_run=true`, backend:

- выполняет только валидацию;
- строит план действий;
- не создаёт сущности в БД;
- возвращает список предполагаемых операций и ошибок.

Пример ответа:

```json
{
  "run_id": null,
  "status": "validated",
  "summary": {
    "org_units_to_create": 5,
    "positions_to_create": 8,
    "employees_to_create": 8,
    "accounts_to_create": 8
  },
  "errors": []
}
```

---

## 13. Раздел: Onboarding runs / deployment status

## 13.1. Назначение

Этот блок нужен для отслеживания прогресса orchestration.

## 13.2. Минимальная модель run

```json
{
  "run_id": "run_001",
  "request_id": "req_20260311_001",
  "client_id": "client_001",
  "status": "running",
  "current_step": "create_positions",
  "progress": 60,
  "started_at": "2026-03-11T10:00:00Z",
  "finished_at": null,
  "error_message": null
}
```

## 13.3. Endpoint'ы

### `GET /api/v1/onboarding-runs/{run_id}`

Назначение: получить текущий статус run.

### `GET /api/v1/onboarding-runs?client_id={client_id}`

Назначение: список запусков по клиенту.

### `GET /api/v1/onboarding-runs/{run_id}/steps`

Назначение: получить детализацию шагов выполнения.

Пример ответа:

```json
{
  "run_id": "run_001",
  "steps": [
    { "code": "create_client", "status": "done" },
    { "code": "create_org_units", "status": "done" },
    { "code": "create_positions", "status": "running" },
    { "code": "create_employees", "status": "pending" },
    { "code": "create_accounts", "status": "pending" }
  ]
}
```

---

## 14. Минимальные схемы DTO для MVP

Ниже — рекомендуемый минимальный состав DTO.

## 14.1. ClientCreateRequest

```json
{
  "code": "string",
  "name": "string",
  "bin": "string",
  "template_id": "string"
}
```

## 14.2. OrgUnitCreateRequest

```json
{
  "client_id": "string",
  "code": "string",
  "name": "string",
  "parent_id": "string|null",
  "unit_type": "department|section|sector"
}
```

## 14.3. PositionCreateRequest

```json
{
  "client_id": "string",
  "org_unit_id": "string",
  "code": "string",
  "name": "string"
}
```

## 14.4. EmployeeCreateRequest

```json
{
  "client_id": "string",
  "last_name": "string",
  "first_name": "string",
  "middle_name": "string|null",
  "email": "string",
  "phone": "string|null",
  "org_unit_id": "string",
  "position_id": "string|null"
}
```

## 14.5. AccountCreateRequest

```json
{
  "employee_id": "string",
  "login": "string",
  "temporary_password": "string",
  "role_codes": ["string"]
}
```

## 14.6. BootstrapEnterpriseRequest

```json
{
  "request_id": "string",
  "client": {},
  "template_id": "string",
  "org_units": [],
  "positions": [],
  "employees": [],
  "options": {
    "create_accounts": true,
    "send_invites": false,
    "dry_run": false
  }
}
```

---

## 15. Минимальные бизнес-валидации

Для baseline v1 необходимо зафиксировать хотя бы следующие правила:

### 15.1. Заказчик

- `code` обязателен и уникален;
- `name` обязателен;
- `bin` обязателен для юрлица, если это поле входит в бизнес-процесс;
- `template_id` должен ссылаться на активный шаблон.

### 15.2. Оргструктура

- коды оргединиц уникальны в пределах клиента;
- `parent_id` или `parent_code` не должны создавать циклическую иерархию;
- `unit_type` должен входить в допустимый словарь.

### 15.3. Должности

- код должности уникален в пределах клиента или оргединицы — правило должно быть выбрано явно;
- должность не может ссылаться на несуществующее подразделение.

### 15.4. Сотрудники

- email обязателен, если создаётся аккаунт;
- сотрудник не может быть привязан к несуществующей должности;
- дубли по email должны обрабатываться предсказуемо: либо запрет, либо merge-policy, но для MVP лучше запрет.

### 15.5. Аккаунты

- один сотрудник — максимум один основной аккаунт в MVP;
- набор `role_codes` должен ссылаться только на допустимые роли.

### 15.6. Bootstrap

- все `org_unit_code`, `position_code`, `external_key` внутри одного запроса должны быть уникальны;
- ссылки сотрудников на `org_unit_code` и `position_code` должны разрешаться внутри этого же payload;
- повторный identical request с тем же request_id не должен создавать дубликаты.

---

## 16. Минимальные статусы onboarding run

**Реализованный словарь статусов run (frozen):**

- `pending` — зарезервировано для async
- `running` — выполняется
- `completed` — успешно завершён
- `failed` — ошибка
- `dry_run` — dry-run завершён, сущности не созданы

**Реализованный словарь статусов step (frozen):**

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

См. `../onboarding/onboarding_statuses_and_error_codes.md` для полного списка error_code.

**Idempotency и dry-run:** см. `../onboarding/onboarding_idempotency_policy.md`, `../onboarding/onboarding_dry_run_contract.md`, `../onboarding/onboarding_api_reference.md`.

---

## 17. Минимальная карта MVP endpoint'ов

Ниже — итоговый перечень baseline endpoint'ов.

### Заказчики

- `GET /api/v1/clients`
- `POST /api/v1/clients`
- `GET /api/v1/clients/{client_id}`
- `PATCH /api/v1/clients/{client_id}`

### Шаблоны предприятий

- `GET /api/v1/enterprise-templates`
- `GET /api/v1/enterprise-templates/{template_id}`
- `GET /api/v1/enterprise-templates/{template_id}/structure-preview`

### Оргструктура

- `GET /api/v1/org-units`
- `GET /api/v1/org-units/tree`
- `POST /api/v1/org-units`
- `PATCH /api/v1/org-units/{org_unit_id}`
- `POST /api/v1/org-units/bulk`

### Должности

- `GET /api/v1/positions`
- `POST /api/v1/positions`
- `PATCH /api/v1/positions/{position_id}`
- `POST /api/v1/positions/bulk`

### Сотрудники

- `GET /api/v1/employees`
- `POST /api/v1/employees`
- `GET /api/v1/employees/{employee_id}`
- `PATCH /api/v1/employees/{employee_id}`
- `POST /api/v1/employees/bulk`

### Аккаунты и роли

- `GET /api/v1/roles`
- `GET /api/v1/accounts`
- `POST /api/v1/accounts`
- `PATCH /api/v1/accounts/{account_id}`
- `POST /api/v1/accounts/bulk`
- `POST /api/v1/accounts/{account_id}/reset-password` — опционально для MVP

### Bootstrap / onboarding

- `POST /api/v1/bootstrap/enterprise`

### Статусы выполнения

- `GET /api/v1/onboarding-runs`
- `GET /api/v1/onboarding-runs/{run_id}`
- `GET /api/v1/onboarding-runs/{run_id}/steps`

---

## 18. Что это даёт проекту прямо сейчас

Фиксация OpenAPI Baseline v1 позволяет немедленно перейти к следующим практическим задачам:

1. Разложить MVP Backlog by Phases по backend, frontend и orchestration.
2. Начать проектирование Pydantic / DTO схем.
3. Начать нарезку backend routers и application services.
4. Начать делать UI-мастер onboarding на фиксированном контракте.
5. Согласовать, что входит в MVP, а что переносится в Phase 2.

То есть это уже не просто концептуальный материал, а операционная основа для разработки.

---

## 19. Рекомендуемый следующий шаг

Следующим документом логично сделать:

# Документ №6. MVP Backlog by Phases

Рекомендуемые фазы:

- **Phase 1** — foundation: справочники, заказчики, шаблоны, базовые CRUD;
- **Phase 2** — org structure + positions + employees;
- **Phase 3** — accounts + roles + minimal auth alignment;
- **Phase 4** — bootstrap/orchestration + onboarding runs;
- **Phase 5** — UI wizard + polish + validation + error states.

Именно на базе этого OpenAPI Baseline v1 бэклог можно разложить уже очень предметно: по endpoint'ам, DTO, сервисам, экранам и acceptance criteria.

---

## 20. Итог

OpenAPI Baseline v1 фиксирует минимальный API-каркас для MVP one-click onboarding предприятия.

Он:

- удерживает фокус на практической реализации;
- не даёт расползтись объёму MVP;
- связывает ERD, мастер-сценарий и будущий backend flow;
- создаёт базу для перехода к backlog и реализации.

На этом уровне проект уже можно переводить из архитектурного описания в управляемый план разработки.

