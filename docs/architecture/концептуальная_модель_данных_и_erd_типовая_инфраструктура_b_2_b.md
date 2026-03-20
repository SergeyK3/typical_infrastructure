# Концептуальная модель данных и ERD

## 1. Назначение документа
Данный документ описывает концептуальную модель данных платформы для быстрого развёртывания корпоративной инфраструктуры B2B-заказчика.

Документ служит основанием для:
- проектирования физической БД;
- подготовки ERD;
- построения API;
- реализации мастер-сценария «создать предприятие»;
- дальнейшего подключения прикладных модулей: тестирования, оценки навыков, задач и обучения.

Цель модели — определить, **какие сущности должны существовать в системе, как они связаны между собой и какие из них являются базовыми для всей платформы**.

---

## 2. Подход к построению модели данных

### 2.1. Базовая идея
Модель данных должна быть разделена на несколько логических контуров:
1. контур заказчиков;
2. инфраструктурный контур;
3. контур идентификации и доступа;
4. шаблонный контур;
5. контур развёртывания;
6. прикладной контур;
7. контур аудита и интеграции.

### 2.2. Архитектурный принцип
Все прикладные модули должны опираться на единые мастер-данные.

Это означает, что сущности:
- заказчик;
- оргединица;
- должность;
- сотрудник;
- кадровое назначение;
- пользовательский аккаунт;
- роль

должны быть централизованными и не дублироваться в отдельных модулях.

### 2.3. Подход к многоарендности
Почти все основные сущности должны быть связаны с заказчиком через `customer_id` или эквивалентный tenant-ключ.

Исключения возможны для:
- глобальных шаблонов;
- глобального справочника ролей платформы;
- глобальных настроек системы.

---

## 3. Логические домены модели

Для проектирования удобно разделить сущности на следующие домены:

### Домен A. Customer / Tenant
- заказчики;
- профиль заказчика;
- отраслевой тип;
- статус;
- активированные модули.

### Домен B. Organization Infrastructure
- оргединицы;
- типы оргединиц;
- должности;
- сотрудники;
- назначения сотрудников.

### Домен C. Identity & Access
- аккаунты;
- роли;
- разрешения;
- области видимости;
- связи аккаунтов и ролей.

### Домен D. Template & Provisioning
- шаблоны предприятий;
- шаблонные подразделения;
- шаблонные должности;
- сценарии развёртывания;
- журналы развёртывания.

### Домен E. Business Modules
- тестирования;
- профили навыков;
- задачи;
- планы обучения.

### Домен F. Audit & Integration
- журнал действий;
- импортные задания;
- внешние соответствия;
- синхронизации.

---

# 4. Сущности домена Customer / Tenant

## 4.1. CustomerCompany

### Назначение
Хранит карточку заказчика как юридического лица или корпоративного клиента в рамках платформы.

### Основные поля
- `customer_id` — PK;
- `code` — внутренний код заказчика;
- `name` — официальное наименование;
- `short_name` — краткое наименование;
- `legal_form` — форма собственности / тип юрлица;
- `industry_code` — отраслевой код;
- `industry_name` — отрасль;
- `bin_iin` или иной идентификатор — при необходимости;
- `status` — active / inactive / archived / onboarding;
- `created_at`;
- `updated_at`.

### Связи
- один заказчик имеет много оргединиц;
- один заказчик имеет много сотрудников;
- один заказчик имеет много аккаунтов;
- один заказчик может иметь несколько активированных модулей;
- один заказчик может быть создан на основе одного шаблона.

---

## 4.2. CustomerProfile

### Назначение
Хранит дополнительные настройки и метаданные заказчика.

### Возможные поля
- `customer_profile_id` — PK;
- `customer_id` — FK;
- `company_size_category`;
- `business_type`;
- `default_timezone`;
- `default_locale`;
- `notes`;
- `onboarding_state`.

### Зачем выделять отдельно
Позволяет не перегружать основную таблицу заказчика и хранить расширяемые параметры отдельно.

---

## 4.3. CustomerModuleActivation

### Назначение
Фиксирует, какие прикладные модули активированы у конкретного заказчика.

### Поля
- `activation_id` — PK;
- `customer_id` — FK;
- `module_code` — assessment / skills / tasks / learning и т.д.;
- `is_enabled`;
- `enabled_at`;
- `settings_json`.

### Значение
Позволяет запускать платформу поэтапно: сначала инфраструктурное ядро, затем отдельные модули.

---

# 5. Сущности домена Organization Infrastructure

## 5.1. OrgUnitType

### Назначение
Справочник типов организационных единиц.

### Примеры значений
- company;
- division;
- department;
- sector;
- section;
- group;
- service;
- production_site.

### Поля
- `org_unit_type_id` — PK;
- `code`;
- `name_ru`;
- `name_en`;
- `description`;
- `is_active`.

---

## 5.2. OrgUnit

### Назначение
Хранит узлы организационной структуры заказчика.

### Поля
- `org_unit_id` — PK;
- `customer_id` — FK;
- `parent_org_unit_id` — nullable FK на OrgUnit;
- `org_unit_type_id` — FK;
- `code` — внутренний код подразделения;
- `name` — название подразделения;
- `full_name` — полное название;
- `sort_order`;
- `is_active`;
- `is_system` — признак автосозданного узла;
- `created_at`;
- `updated_at`.

### Связи
- один заказчик имеет много оргединиц;
- одна оргединица может иметь много дочерних оргединиц;
- одна оргединица может иметь много должностей;
- одна оргединица может иметь много назначений сотрудников.

### Ключевой принцип
Оргструктура должна быть древовидной и поддерживать несколько уровней вложенности.

---

## 5.3. Position

### Назначение
Справочник должностей, доступных в системе.

### Поля
- `position_id` — PK;
- `customer_id` — nullable FK, если часть должностей глобальные, а часть локальные;
- `code`;
- `name`;
- `category` — руководящая / экспертная / исполнительская / административная;
- `grade_level` — при необходимости;
- `is_managerial`;
- `is_active`;
- `created_at`;
- `updated_at`.

### Комментарий
Возможны два подхода:
1. только локальные должности заказчика;
2. глобальный справочник + локальные переопределения.

Для старта MVP допустим более простой вариант — должности в контуре конкретного заказчика.

---

## 5.4. OrgUnitPositionBinding

### Назначение
Связывает должности с конкретными подразделениями.

### Почему нужен отдельный объект
Одна и та же должность может встречаться в разных подразделениях, а одно подразделение может включать много должностей.

### Поля
- `binding_id` — PK;
- `customer_id` — FK;
- `org_unit_id` — FK;
- `position_id` — FK;
- `headcount_planned` — плановое количество единиц;
- `is_active`;
- `created_at`.

### Связь
- many-to-many между OrgUnit и Position.

---

## 5.5. Employee

### Назначение
Хранит физическое лицо как сотрудника заказчика.

### Поля
- `employee_id` — PK;
- `customer_id` — FK;
- `last_name`;
- `first_name`;
- `middle_name`;
- `full_name`;
- `person_code` или `employee_code`;
- `email`;
- `phone`;
- `birth_date` — опционально, если это допустимо политикой данных;
- `is_active`;
- `created_at`;
- `updated_at`.

### Комментарий
На концептуальном уровне Employee — это человек, а не его текущая должность.

---

## 5.6. EmploymentAssignment

### Назначение
Хранит факт кадрового назначения сотрудника в подразделение и на должность.

### Это одна из ключевых сущностей всей платформы.

### Поля
- `assignment_id` — PK;
- `customer_id` — FK;
- `employee_id` — FK;
- `org_unit_id` — FK;
- `position_id` — FK;
- `binding_id` — nullable FK на OrgUnitPositionBinding;
- `employment_type` — основное место / совместительство / временное назначение;
- `assignment_role` — руководитель / сотрудник / куратор и т.д.;
- `date_from`;
- `date_to` — nullable;
- `is_primary`;
- `is_active`;
- `created_at`;
- `updated_at`.

### Почему это критично
Именно эта сущность позволяет:
- переводить сотрудника между подразделениями;
- учитывать историю назначений;
- поддерживать совмещение;
- связывать прикладные действия с реальной кадровой позицией, а не только с карточкой человека.

---

# 6. Сущности домена Identity & Access

## 6.1. UserAccount

### Назначение
Учётная запись пользователя платформы.

### Поля
- `user_id` — PK;
- `customer_id` — nullable FK, если есть глобальные платформенные админы;
- `employee_id` — nullable FK, если аккаунт связан с сотрудником;
- `login`;
- `password_hash`;
- `email`;
- `phone`;
- `account_status` — active / blocked / invited / archived;
- `last_login_at`;
- `must_change_password`;
- `created_at`;
- `updated_at`.

### Важный момент
Не каждый сотрудник обязан сразу иметь аккаунт, и не каждый аккаунт обязан быть связан с обычным сотрудником. Например, платформенный супер-администратор может быть глобальным пользователем.

---

## 6.2. Role

### Назначение
Справочник ролей доступа.

### Поля
- `role_id` — PK;
- `code`;
- `name_ru`;
- `name_en`;
- `role_scope_type` — platform / customer / org_unit / module;
- `is_system`;
- `is_active`.

### Примеры ролей
- PLATFORM_SUPER_ADMIN;
- CUSTOMER_SYS_ADMIN;
- IMPLEMENTATION_OPERATOR;
- ORG_HEAD;
- EMPLOYEE;
- ASSESSMENT_EXPERT;
- LEARNING_MANAGER.

---

## 6.3. Permission

### Назначение
Справочник атомарных разрешений.

### Поля
- `permission_id` — PK;
- `code`;
- `name_ru`;
- `module_code`;
- `action_code` — create / read / update / delete / assign / deploy и т.п.;
- `description`;
- `is_active`.

---

## 6.4. RolePermission

### Назначение
Связь ролей и разрешений.

### Поля
- `role_permission_id` — PK;
- `role_id` — FK;
- `permission_id` — FK;
- `is_allowed`.

### Связь
- many-to-many между Role и Permission.

---

## 6.5. UserRoleAssignment

### Назначение
Назначение ролей конкретным аккаунтам.

### Поля
- `user_role_assignment_id` — PK;
- `user_id` — FK;
- `role_id` — FK;
- `customer_id` — nullable FK;
- `org_unit_id` — nullable FK;
- `module_code` — nullable;
- `date_from`;
- `date_to` — nullable;
- `is_active`.

### Зачем нужны customer_id и org_unit_id здесь
Чтобы одну и ту же роль можно было ограничивать контекстом действия.

Например:
- пользователь является CUSTOMER_SYS_ADMIN только в рамках одного заказчика;
- пользователь является ORG_HEAD только в рамках определённого подразделения.

---

## 6.6. AccessScope

### Назначение
Дополнительная модель видимости данных.

### Поля
- `scope_id` — PK;
- `user_id` — FK;
- `scope_type` — customer / org_tree / org_unit / self / module;
- `customer_id` — nullable FK;
- `org_unit_id` — nullable FK;
- `include_children` — boolean;
- `scope_rules_json`.

### Почему лучше выделить отдельно
RBAC отвечает на вопрос «что можно делать», а AccessScope — «в каком контуре это видно».

---

# 7. Сущности домена Template & Provisioning

## 7.1. EnterpriseTemplate

### Назначение
Корневой объект шаблона предприятия.

### Поля
- `template_id` — PK;
- `code`;
- `name`;
- `description`;
- `industry_hint`;
- `is_active`;
- `version`;
- `created_at`;
- `updated_at`.

### Примеры
- GENERIC_COMPANY;
- MANUFACTURING_COMPANY;
- FURNITURE_FACTORY;
- SERVICE_COMPANY.

---

## 7.2. TemplateOrgUnit

### Назначение
Шаблонный узел оргструктуры.

### Поля
- `template_org_unit_id` — PK;
- `template_id` — FK;
- `parent_template_org_unit_id` — nullable FK;
- `org_unit_type_code`;
- `code`;
- `name`;
- `is_required`;
- `default_sort_order`;
- `is_enabled_by_default`.

### Назначение
Позволяет описать структуру предприятия до фактического развёртывания.

---

## 7.3. TemplatePosition

### Назначение
Шаблонная должность, которая создаётся при развёртывании предприятия.

### Поля
- `template_position_id` — PK;
- `template_id` — FK;
- `template_org_unit_id` — nullable FK;
- `code`;
- `name`;
- `category`;
- `is_managerial`;
- `is_required`;
- `headcount_planned`.

---

## 7.4. TemplateRole

### Назначение
Описывает стартовые ролевые назначения и рекомендуемую модель доступа для шаблона.

### Поля
- `template_role_id` — PK;
- `template_id` — FK;
- `role_code`;
- `assign_to` — system_admin / unit_head / employee / manual;
- `scope_type`;
- `is_required`.

---

## 7.5. TemplateDeploymentScenario

### Назначение
Хранит шаги или конфигурацию сценария развёртывания.

### Поля
- `scenario_id` — PK;
- `template_id` — FK;
- `scenario_code`;
- `steps_json` или нормализованный набор шагов;
- `is_default`;
- `version`.

---

## 7.6. DeploymentRun

### Назначение
Фиксирует конкретный запуск развёртывания предприятия.

### Поля
- `deployment_run_id` — PK;
- `customer_id` — FK;
- `template_id` — FK;
- `started_by_user_id` — FK;
- `status` — running / completed / failed / partial;
- `started_at`;
- `completed_at`;
- `result_summary_json`.

---

## 7.7. DeploymentStep

### Назначение
Фиксирует шаги конкретного запуска развёртывания.

### Поля
- `deployment_step_id` — PK;
- `deployment_run_id` — FK;
- `step_code`;
- `step_order`;
- `status`;
- `started_at`;
- `completed_at`;
- `message`;
- `details_json`.

### Примеры шагов
- create_customer;
- create_root_org_unit;
- create_default_departments;
- create_default_positions;
- create_system_admin;
- assign_roles.

---

# 8. Сущности прикладного домена

На данном этапе они фиксируются только концептуально, чтобы не потерять архитектурную совместимость.

## 8.1. AssessmentSession

### Назначение
Сессия тестирования или психологической диагностики.

### Поля
- `assessment_session_id` — PK;
- `customer_id` — FK;
- `employee_id` — FK;
- `assignment_id` — nullable FK;
- `assessment_type_code`;
- `started_at`;
- `completed_at`;
- `status`;
- `result_json`.

### Почему нужен assignment_id
Результат иногда важно связывать не только с человеком, но и с его текущей ролью/назначением.

---

## 8.2. SkillProfile

### Назначение
Профиль навыков сотрудника.

### Поля
- `skill_profile_id` — PK;
- `customer_id` — FK;
- `employee_id` — FK;
- `assignment_id` — nullable FK;
- `profile_date`;
- `profile_status`;
- `overall_score`;
- `details_json`.

---

## 8.3. Task

### Назначение
Задача в системе контроля исполнения.

### Поля
- `task_id` — PK;
- `customer_id` — FK;
- `created_by_user_id` — FK;
- `assigned_to_user_id` — nullable FK;
- `assigned_to_assignment_id` — nullable FK;
- `org_unit_id` — nullable FK;
- `title`;
- `description`;
- `status`;
- `priority`;
- `due_at`;
- `created_at`;
- `updated_at`.

### Комментарий
В зрелой модели задачу лучше уметь назначать не только аккаунту, но и кадровому назначению / организационному месту.

---

## 8.4. LearningPlan

### Назначение
Индивидуальный или групповой план обучения.

### Поля
- `learning_plan_id` — PK;
- `customer_id` — FK;
- `employee_id` — FK;
- `assignment_id` — nullable FK;
- `plan_type`;
- `source_type` — manual / assessment / skills_gap / role_requirement;
- `status`;
- `start_date`;
- `end_date`;
- `summary`.

---

## 8.5. TrainingAssignment

### Назначение
Назначение конкретного учебного элемента сотруднику.

### Поля
- `training_assignment_id` — PK;
- `customer_id` — FK;
- `learning_plan_id` — FK;
- `employee_id` — FK;
- `course_code` или `learning_item_id`;
- `status`;
- `due_date`;
- `completed_at`;
- `result_score`.

---

# 9. Сущности домена Audit & Integration

## 9.1. AuditLog

### Назначение
Журнал административных и значимых действий.

### Поля
- `audit_log_id` — PK;
- `customer_id` — nullable FK;
- `actor_user_id` — nullable FK;
- `entity_type`;
- `entity_id`;
- `action_code`;
- `action_result`;
- `occurred_at`;
- `payload_json`.

---

## 9.2. ImportJob

### Назначение
Фиксирует задание на импорт.

### Поля
- `import_job_id` — PK;
- `customer_id` — FK;
- `import_type` — org_units / positions / employees / accounts;
- `started_by_user_id` — FK;
- `status`;
- `source_file_name`;
- `started_at`;
- `completed_at`;
- `summary_json`.

---

## 9.3. ImportError

### Назначение
Хранит ошибки импорта.

### Поля
- `import_error_id` — PK;
- `import_job_id` — FK;
- `row_number`;
- `field_name`;
- `error_code`;
- `error_message`;
- `raw_value`.

---

## 9.4. ExternalMapping

### Назначение
Связь внутренних сущностей платформы с идентификаторами внешних систем.

### Поля
- `external_mapping_id` — PK;
- `customer_id` — FK;
- `external_system_code`;
- `entity_type`;
- `internal_entity_id`;
- `external_entity_id`;
- `mapping_status`;
- `last_synced_at`.

---

# 10. Ключевые связи между сущностями

Ниже перечислены основные связи предметной модели.

## 10.1. CustomerCompany → OrgUnit
- один заказчик имеет много оргединиц.

## 10.2. OrgUnit → OrgUnit
- одна оргединица может иметь много дочерних оргединиц;
- связь иерархическая self-reference.

## 10.3. CustomerCompany → Position
- один заказчик имеет много должностей.

## 10.4. OrgUnit ↔ Position через OrgUnitPositionBinding
- many-to-many связь между подразделениями и должностями.

## 10.5. CustomerCompany → Employee
- один заказчик имеет много сотрудников.

## 10.6. Employee → EmploymentAssignment
- один сотрудник может иметь много кадровых назначений во времени.

## 10.7. OrgUnit → EmploymentAssignment
- одна оргединица может иметь много назначений сотрудников.

## 10.8. Position → EmploymentAssignment
- одна должность может участвовать во множестве назначений.

## 10.9. Employee ↔ UserAccount
- связь один-к-одному или один-к-нулю/одному;
- сотрудник может не иметь аккаунта;
- глобальный пользователь может не иметь employee_id.

## 10.10. UserAccount ↔ Role через UserRoleAssignment
- many-to-many с контекстом действия.

## 10.11. Role ↔ Permission через RolePermission
- many-to-many.

## 10.12. EnterpriseTemplate → TemplateOrgUnit
- один шаблон имеет много шаблонных оргединиц.

## 10.13. EnterpriseTemplate → TemplatePosition
- один шаблон имеет много шаблонных должностей.

## 10.14. CustomerCompany → DeploymentRun
- у заказчика может быть один или несколько запусков развёртывания.

## 10.15. DeploymentRun → DeploymentStep
- один запуск состоит из многих шагов.

## 10.16. Employee / Assignment → Business Modules
- прикладные сущности должны ссылаться на сотрудника и, при необходимости, на кадровое назначение.

---

# 11. Концептуальный ERD в текстовом виде

Ниже представлено текстовое описание ERD на концептуальном уровне.

## 11.1. Центральная ось платформы
`CustomerCompany`
→ имеет `OrgUnit`
→ имеет `Position`
→ имеет `Employee`
→ имеет `UserAccount`
→ имеет `CustomerModuleActivation`

## 11.2. Организационная ось
`OrgUnit`
→ имеет родителя `OrgUnit`
→ связывается с `Position` через `OrgUnitPositionBinding`
→ участвует в `EmploymentAssignment`

## 11.3. Кадровая ось
`Employee`
→ имеет одно или более `EmploymentAssignment`
→ может иметь `UserAccount`
→ может участвовать в `AssessmentSession`, `SkillProfile`, `Task`, `LearningPlan`

## 11.4. Ось доступа
`UserAccount`
→ получает роли через `UserRoleAssignment`
`Role`
→ получает разрешения через `RolePermission`
`UserAccount`
→ может иметь `AccessScope`

## 11.5. Ось шаблонов
`EnterpriseTemplate`
→ имеет `TemplateOrgUnit`
→ имеет `TemplatePosition`
→ имеет `TemplateRole`
→ имеет `TemplateDeploymentScenario`

## 11.6. Ось развёртывания
`DeploymentRun`
→ относится к `CustomerCompany`
→ использует `EnterpriseTemplate`
→ состоит из `DeploymentStep`

## 11.7. Ось прикладных модулей
`AssessmentSession`, `SkillProfile`, `Task`, `LearningPlan`, `TrainingAssignment`
→ ссылаются на `CustomerCompany`
→ ссылаются на `Employee`
→ при необходимости ссылаются на `EmploymentAssignment`

---

# 12. Минимальный состав таблиц для MVP

Если выделить только минимально необходимый костяк для первой рабочей версии, то в MVP целесообразно включить:

## 12.1. Обязательные таблицы MVP
- customer_company;
- customer_profile;
- org_unit_type;
- org_unit;
- position;
- org_unit_position_binding;
- employee;
- employment_assignment;
- user_account;
- role;
- permission;
- role_permission;
- user_role_assignment;
- access_scope;
- enterprise_template;
- template_org_unit;
- template_position;
- deployment_run;
- deployment_step;
- audit_log.

## 12.2. Что можно отложить на фазу 2
- customer_module_activation;
- template_role;
- template_deployment_scenario;
- import_job;
- import_error;
- external_mapping;
- все прикладные сущности кроме одной пилотной группы.

---

# 13. Важные проектные решения, которые желательно закрепить заранее

## 13.1. Employee и Assignment должны быть разными сущностями
Это нужно оставить как обязательное правило.

## 13.2. Role и AccessScope должны быть разведены
Иначе будет трудно реализовать видимость по оргструктуре.

## 13.3. Шаблоны должны быть отдельными сущностями, а не зашитой логикой в коде
Иначе быстро потеряется гибкость.

## 13.4. Все прикладные модули должны ссылаться на инфраструктурное ядро
Дублирование сотрудников, подразделений и ролей недопустимо.

## 13.5. В большинстве рабочих таблиц нужен customer_id
Это основной механизм изоляции данных по заказчикам в стартовой архитектуре.

---

# 14. Рекомендуемая следующая детализация

После этой концептуальной модели логично сделать ещё два связанных документа:

## 14.1. Физическая ERD / draft database schema
Там уже можно определить:
- типы данных;
- PK/FK;
- ограничения;
- индексы;
- обязательность полей;
- уникальные ключи.

## 14.2. Мастер-сценарий «создать предприятие»
Там уже нужно описать:
- входные параметры;
- последовательность шагов;
- правила валидации;
- ошибки;
- rollback / повторный запуск;
- ожидаемый результат.

---

# 15. Итог

Концептуальная модель показывает, что ядро вашей платформы должно опираться не на прикладной модуль, а на устойчивый организационный фундамент:
- заказчик;
- оргструктура;
- должности;
- сотрудники;
- кадровые назначения;
- аккаунты;
- роли;
- области видимости;
- шаблоны развёртывания.

Именно этот фундамент позволит быстро создавать новое предприятие, редактировать его структуру и затем без лишнего ручного труда подключать психологическое тестирование, диагностику навыков, задачи и персональные программы обучения.

