# Документ №10. Delivery Board / Work Breakdown v1

## 1. Назначение документа

Delivery Board / Work Breakdown v1 переводит архитектурный пакет и implementation sequence в управляемую структуру исполнения.

Если предыдущие документы отвечали на вопросы:

- что строим;
- из каких слоёв состоит система;
- в каком порядке её реализовывать,

то этот документ отвечает на следующий практический вопрос:

**на какие конкретные пакеты работ нужно разложить MVP, в какой зависимости они находятся, что может идти параллельно, а что должно выполняться строго последовательно.**

Это уже не просто архитектурный и не просто delivery-документ. Это первый рабочий контур управленческого backlog.

---

## 2. Что именно должен дать этот документ

Документ должен зафиксировать:

- верхнеуровневые эпики MVP;
- пакеты работ внутри каждого эпика;
- зависимости между пакетами;
- порядок открытия работ;
- минимальные deliverables по каждому пакету;
- definition of done на уровне work package;
- demo/checkpoint точки;
- то, что может выполняться параллельно;
- то, что не должно стартовать раньше времени.

Именно этот уровень обычно используется как переход от архитектуры к реальному execution management.

---

## 3. Базовый принцип разбиения работ

Работы нужно делить не по «красивым названиям модулей» и не по таблицам БД, а по единицам поставки, которые можно:

- реализовать;
- проверить;
- продемонстрировать;
- принять как завершённый инкремент.

Поэтому структура разбиения должна быть трёхуровневой:

1. **Epic** — крупный контур поставки;
2. **Work Package** — завершённый пакет работ внутри эпика;
3. **Task Cluster** — группа конкретных инженерных задач внутри пакета.

На уровне этого документа фиксируем первые два уровня: Epic и Work Package.

---

## 4. Верхнеуровневая структура MVP Board

Рекомендуемая структура board для MVP:

- E1. Baseline and Governance
- E2. Core Foundation
- E3. API and Reference CRUD Baseline
- E4. Organization Structure
- E5. Positions and Staffing
- E6. Accounts and Role Assignment
- E7. Onboarding Runs and Process Visibility
- E8. Bootstrap Orchestration and Wizard
- E9. Hardening, Pilot Readiness and Stabilization

Ниже — раскрытие этих эпиков.

---

## 5. E1 — Baseline and Governance

### Цель эпика

Зафиксировать правила, без которых дальнейшая реализация начнёт расползаться по терминологии, контрактам и стилям поставки.

### Work Packages

#### E1-WP1. Terminology and Domain Baseline

Состав:

- согласование терминов client / org unit / position / employee / account / role / onboarding run;
- фиксация naming conventions;
- фиксация границ MVP.

Deliverable:

- единый терминологический словарь и список MVP-сущностей.

Definition of done:

- нет противоречия между архитектурой, ERD и API baseline.

#### E1-WP2. Contract Policy Baseline

Состав:

- правила DTO naming;
- правила request/response format;
- error model baseline;
- pagination/filter conventions.

Deliverable:

- зафиксированная API policy для MVP.

Definition of done:

- backend и frontend используют согласованные базовые правила контрактов.

#### E1-WP3. Delivery Governance Baseline

Состав:

- порядок delivery waves;
- правила открытия следующих работ;
- commit discipline;
- migration discipline;
- demo cadence.

Deliverable:

- управленческие правила поставки MVP.

Definition of done:

- sequence и work breakdown не конфликтуют друг с другом.

### Зависимости

E1 должен быть завершён или как минимум зафиксирован в baseline-версии до активной разработки бизнес-сущностей.

---

## 6. E2 — Core Foundation

### Цель эпика

Построить технический каркас backend и frontend, пригодный для безопасного наращивания функциональности.

### Work Packages

#### E2-WP1. Backend Runtime Foundation

Состав:

- структура backend-модулей;
- app bootstrap;
- config handling;
- dependency wiring;
- logging baseline;
- health endpoints.

Deliverable:

- backend foundation runtime.

Definition of done:

- сервис предсказуемо запускается и поддерживает базовый цикл разработки.

#### E2-WP2. Database Migration Foundation

Состав:

- базовый migration flow;
- правила ревизий;
- стартовые миграции foundation-уровня;
- dev/test reset strategy.

Deliverable:

- воспроизводимый контур миграций.

Definition of done:

- чистая БД может быть поднята и доведена до актуального состояния предсказуемо.

#### E2-WP3. Frontend Shell Foundation

Состав:

- app shell;
- layout;
- section navigation;
- auth-aware routing;
- page frame;
- common feedback zones.

Deliverable:

- базовый интерфейсный каркас.

Definition of done:

- новые разделы можно подключать в единый shell без ad hoc решений.

#### E2-WP4. Frontend Integration Foundation

Состав:

- API client;
- query/cache layer;
- standard error handling;
- common loading/empty/error states;
- toast/confirmation pattern.

Deliverable:

- единый клиентский интеграционный foundation.

Definition of done:

- frontend умеет стабильно работать с backend-контрактами базового уровня.

### Зависимости

E2 может идти почти сразу после E1 и частично параллельно внутри backend/frontend.

---

## 7. E3 — API and Reference CRUD Baseline

### Цель эпика

Создать эталонный сквозной контур API + backend + frontend на простых сущностях.

### Work Packages

#### E3-WP1. Reference Entity Model and Migration

Состав:

- таблицы reference-сущностей первой волны;
- модели;
- миграции.

Deliverable:

- reference data layer в БД.

Definition of done:

- сущности существуют в схеме и соответствуют API baseline.

#### E3-WP2. Reference CRUD Backend Slice

Состав:

- repositories;
- services;
- routers;
- DTO list/detail/create/update/delete.

Deliverable:

- первый стабильный CRUD slice на backend.

Definition of done:

- API проходит ручную и/или автоматизированную проверку end-to-end.

#### E3-WP3. Reference CRUD Frontend Slice

Состав:

- list page;
- create/edit form;
- delete/deactivate flow;
- standard filters/search.

Deliverable:

- первый эталонный CRUD-экран.

Definition of done:

- пользователь может полностью пройти CRUD-цикл через UI.

#### E3-WP4. Contract Freeze A

Состав:

- стабилизация envelope shape;
- validation error contract;
- list response convention;
- mutation response convention.

Deliverable:

- первая точка фиксации API/UI контракта.

Definition of done:

- следующие CRUD-пакеты опираются на единый эталон.

### Зависимости

E3 зависит от E1 и E2.

---

## 8. E4 — Organization Structure

### Цель эпика

Реализовать рабочий контур организационной структуры клиента.

### Work Packages

#### E4-WP1. Org Units Data Model

Состав:

- таблица org units;
- parent-child relationship;
- constraints;
- миграции.

Deliverable:

- иерархическая модель подразделений.

Definition of done:

- схема данных отражает базовую оргструктуру без логических конфликтов.

#### E4-WP2. Org Units Backend Services

Состав:

- list/detail/create/update services;
- parent validation;
- activation/deactivation;
- tree or flat retrieval logic.

Deliverable:

- backend-контур оргструктуры.

Definition of done:

- org units можно безопасно создавать и редактировать через API.

#### E4-WP3. Org Units Frontend Workspace

Состав:

- hierarchy workspace;
- tree/table rendering;
- create root/child flows;
- edit flow;
- activation/deactivation UI.

Deliverable:

- рабочее пространство управления оргструктурой.

Definition of done:

- пользователь может собрать и править структуру компании через UI.

#### E4-WP4. Org Structure Acceptance Pass

Состав:

- сквозная проверка CRUD + hierarchy rendering;
- проверка связности с клиентом;
- проверка базовых destructive scenarios.

Deliverable:

- принятая org structure slice.

Definition of done:

- оргструктурный слой считается стабильной опорой для staffing-фазы.

### Зависимости

E4 должен завершиться до старта полноценной staffing-модели.

---

## 9. E5 — Positions and Staffing

### Цель эпика

Собрать кадрово-штатный контур: должности и сотрудники внутри оргструктуры.

### Work Packages

#### E5-WP1. Positions Data and Backend Slice

Состав:

- positions schema;
- связи с org units;
- CRUD backend;
- list/detail DTO.

Deliverable:

- backend-контур должностей.

Definition of done:

- должности можно создавать и связывать с подразделениями.

#### E5-WP2. Positions UI Slice

Состав:

- positions list;
- form create/edit;
- фильтр по подразделению;
- activation/deactivation.

Deliverable:

- UI управления должностями.

Definition of done:

- пользователь управляет должностями без ручных обходов.

#### E5-WP3. Employees Data and Backend Slice

Состав:

- employees schema;
- связи с org units / positions;
- CRUD backend;
- list/detail DTO.

Deliverable:

- backend-контур сотрудников.

Definition of done:

- сотрудник как сущность стабилен на API-уровне.

#### E5-WP4. Employees UI Slice

Состав:

- employees list;
- search;
- employee form;
- отображение связей employee ↔ position ↔ org unit.

Deliverable:

- UI управления сотрудниками.

Definition of done:

- кадровая запись управляется через UI и не смешивается с account-layer.

#### E5-WP5. Contract Freeze B

Состав:

- стабилизация DTO по org unit / position / employee;
- стабилизация linking conventions.

Deliverable:

- фиксированная кадрово-организационная contract base.

Definition of done:

- account/role слой может начинаться без постоянной переделки staffing-DTO.

### Зависимости

E5 зависит от E4 и частично от E3 pattern baseline.

---

## 10. E6 — Accounts and Role Assignment

### Цель эпика

Добавить системный слой аккаунтов и назначений ролей поверх кадровой модели.

### Work Packages

#### E6-WP1. Accounts Data and Backend Slice

Состав:

- accounts schema;
- account lifecycle baseline;
- account link to employee, если входит в MVP;
- CRUD / detail API.

Deliverable:

- backend-контур аккаунтов.

Definition of done:

- аккаунты существуют как управляемая системная сущность.

#### E6-WP2. Role Assignment Backend Slice

Состав:

- role dictionaries/templates, если нужны;
- account-role assignment model;
- assign/revoke services;
- validation against duplicates/conflicts.

Deliverable:

- backend-контур назначения ролей.

Definition of done:

- роли можно назначать и отзывать по стабильному контракту.

#### E6-WP3. Accounts and Roles UI Workspace

Состав:

- account list/detail;
- role assignment panel;
- revoke/deactivate actions;
- readable role presentation.

Deliverable:

- UI управления доступами.

Definition of done:

- пользователь может прозрачно управлять аккаунтом и ролями.

#### E6-WP4. Access Model Acceptance Pass

Состав:

- сквозная проверка employee ↔ account ↔ role;
- проверка дублей;
- проверка UX понятности назначения ролей.

Deliverable:

- принятый access-layer.

Definition of done:

- process-layer может опираться на account-role модель.

### Зависимости

E6 зависит от E5.

---

## 11. E7 — Onboarding Runs and Process Visibility

### Цель эпика

Сделать процесс onboarding наблюдаемым как отдельный слой системы.

### Work Packages

#### E7-WP1. Onboarding Run Data Model

Состав:

- onboarding_runs schema;
- статусы;
- step/stage tracking;
- result/error payload support.

Deliverable:

- модель процесса onboarding.

Definition of done:

- процесс имеет собственную диагностируемую сущность выполнения.

#### E7-WP2. Onboarding Run Backend Slice

Состав:

- list/detail/status endpoints;
- result representation;
- error representation;
- retrievable history baseline.

Deliverable:

- backend видимости процесса.

Definition of done:

- API возвращает run как наблюдаемую процессную сущность.

#### E7-WP3. Onboarding Runs UI

Состав:

- runs list;
- run detail;
- status rendering;
- errors/partial results rendering.

Deliverable:

- UI наблюдения за onboarding-процессом.

Definition of done:

- пользователь видит процесс, а не только факт запуска.

#### E7-WP4. Contract Freeze C

Состав:

- стабилизация process state model;
- стабилизация run/result DTO;
- фиксация error presentation contract.

Deliverable:

- стабильный process visibility contract.

Definition of done:

- wizard может безопасно опираться на run/result layer.

### Зависимости

E7 зависит от E6 и от baseline-паттернов E3.

---

## 12. E8 — Bootstrap Orchestration and Wizard

### Цель эпика

Реализовать главный сценарий продукта: one-click onboarding с orchestration-командой и мастером.

### Work Packages

#### E8-WP1. Bootstrap Command Contract

Состав:

- orchestration payload schema;
- command validation policy;
- idempotency approach;
- success/failure result shape.

Deliverable:

- формализованный orchestration contract.

Definition of done:

- команда запуска описана и проверяема на уровне API.

#### E8-WP2. Bootstrap Backend Orchestration Slice

Состав:

- orchestration service;
- orchestration endpoint;
- integration with onboarding_runs;
- partial failure handling.

Deliverable:

- backend one-click orchestration.

Definition of done:

- система принимает команду и запускает управляемый процесс.

#### E8-WP3. Wizard Draft and Step Model

Состав:

- wizard structure;
- step definitions;
- draft state;
- summary/review model.

Deliverable:

- скелет мастера как управляемого UI-сценария.

Definition of done:

- мастер имеет устойчивую внутреннюю модель, а не набор случайных форм.

#### E8-WP4. Wizard UI and Submit Flow

Состав:

- step UI;
- review step;
- submit action;
- success/failure summary;
- link to run detail.

Deliverable:

- UI one-click onboarding.

Definition of done:

- пользователь проходит сценарий от начала до запуска процесса.

#### E8-WP5. Contract Freeze D

Состав:

- стабилизация wizard-submit contract;
- стабилизация result feedback model;
- фиксация UX поведения на ошибках.

Deliverable:

- зафиксированный orchestration/wizard contract.

Definition of done:

- главный MVP-сценарий перестаёт быть экспериментальным.

### Зависимости

E8 зависит от E7 и всей стабилизированной базы E4–E6.

---

## 13. E9 — Hardening, Pilot Readiness and Stabilization

### Цель эпика

Довести весь MVP до состояния, пригодного для пилотной эксплуатации и демонстрации без постоянного ручного сопровождения.

### Work Packages

#### E9-WP1. Backend Hardening

Состав:

- contract cleanup;
- error model cleanup;
- destructive-operation safeguards;
- observability improvements;
- performance sanity checks.

Deliverable:

- устойчивый backend MVP.

Definition of done:

- основные backend-разрывы и контрактные шероховатости устранены.

#### E9-WP2. Frontend Hardening

Состав:

- polish empty/loading/error states;
- better navigation continuity;
- better mutation feedback;
- race condition cleanup;
- label/text cleanup.

Deliverable:

- устойчивый frontend MVP.

Definition of done:

- пользовательский контур выглядит собранным и предсказуемым.

#### E9-WP3. Smoke and Acceptance Suite

Состав:

- минимальные smoke сценарии;
- сквозной happy path;
- базовые regression checks по ключевым разделам.

Deliverable:

- защитный acceptance-контур MVP.

Definition of done:

- основной сценарий проверяется не только вручную, но и повторяемо.

#### E9-WP4. Pilot Readiness Checkpoint

Состав:

- итоговая проверка key flows;
- проверка demo narrative;
- проверка списка известных ограничений MVP.

Deliverable:

- решение о pilot readiness.

Definition of done:

- система готова к пилотной демонстрации как единый продуктовый контур.

### Зависимости

E9 начинается после завершения основного orchestration-сценария E8.

---

## 14. Что может идти параллельно

Не все работы обязаны идти строго линейно.

### Может идти параллельно при соблюдении зависимостей:

- E2-WP1 и E2-WP3;
- E2-WP2 и E2-WP4;
- внутри E3 backend slice и подготовка frontend reusable UI;
- внутри E5 positions backend и проектирование employees UI patterns, если contract assumptions уже понятны;
- внутри E8 проектирование wizard step-model может частично начаться до полной UI-сборки, но не до стабилизации run-contract.

### Не должно идти преждевременно:

- полноценный wizard UI до E7;
- role assignment до стабилизации staffing layer;
- process-layer без формальной run-model;
- pilot hardening до появления сквозного happy path.

---

## 15. Порядок открытия work packages

Рекомендуемый порядок открытия работ:

1. сначала открыть все E1 work packages;
2. затем foundation E2;
3. затем только один эталонный CRUD slice из E3;
4. после acceptance E3 открыть E4;
5. затем открыть E5 пакетами positions → employees;
6. затем E6;
7. затем E7;
8. затем E8;
9. затем E9.

Внутри каждого эпика желательно не распыляться на слишком много одновременно открытых work packages, если они опираются на одни и те же нестабильные контракты.

---

## 16. Dependency map в кратком виде

Ниже — короткая dependency-цепочка:

- E1 → E2 → E3
- E3 → E4
- E4 → E5
- E5 → E6
- E6 → E7
- E7 → E8
- E8 → E9

Поперечные зависимости:

- Contract Freeze A поддерживает E4–E9;
- Contract Freeze B поддерживает E6–E9;
- Contract Freeze C поддерживает E8–E9;
- Contract Freeze D закрывает стабилизацию главного MVP-сценария.

---

## 17. Demo and checkpoint board

Для управления поставкой полезно зафиксировать контрольные точки.

### Checkpoint 1 — Foundation Ready

- E1 и E2 завершены в baseline-объёме.

### Checkpoint 2 — First CRUD Ready

- E3 завершён и принят.

### Checkpoint 3 — Org Structure Ready

- E4 завершён.

### Checkpoint 4 — Staffing Ready

- E5 завершён.

### Checkpoint 5 — Access Ready

- E6 завершён.

### Checkpoint 6 — Process Visibility Ready

- E7 завершён.

### Checkpoint 7 — Main Scenario Ready

- E8 завершён.

### Checkpoint 8 — Pilot Ready

- E9 завершён в минимально достаточном объёме.

---

## 18. Формат рабочего board-представления

Практически этот work breakdown потом можно переложить в Kanban или roadmap-board в таком формате:

- **Column 1:** Planned
- **Column 2:** Ready to Start
- **Column 3:** In Progress
- **Column 4:** Review / Acceptance
- **Column 5:** Frozen / Accepted
- **Column 6:** Blocked
- **Column 7:** Done

Единицей движения по board желательно делать именно **Work Package**, а не разрозненные мелкие задачи.

Это позволит управлять не хаотичным потоком микроактивностей, а поставкой завершённых инкрементов.

---

## 19. Минимальная карточка Work Package

Для каждого work package желательно потом использовать единую карточку со следующими полями:

- ID;
- Epic;
- название;
- цель;
- scope;
- dependencies;
- deliverable;
- definition of done;
- demo/checkpoint relation;
- owner;
- status;
- notes/risks.

На уровне этого документа эта карточка пока не заполняется по каждому элементу полностью, но структура уже должна быть понятна.

---

## 20. Типовые риски плохого work breakdown

### 20.1. Слишком крупные пакеты

Результат:

- невозможно понять, что реально завершено;
- review и acceptance затягиваются;
- прогресс становится формальным.

### 20.2. Слишком мелкое дробление

Результат:

- board превращается в список микроопераций;
- теряется управляемость delivery-инкрементами;
- demo milestones размываются.

### 20.3. Открытие зависимых пакетов раньше времени

Результат:

- постоянные блокировки;
- переделки контрактов;
- рост технического шума.

### 20.4. Отсутствие definition of done

Результат:

- пакет считается «почти готовым» слишком долго;
- фактическая готовность неочевидна.

---

## 21. Итоговая матрица эпиков и пакетов

| Epic | Смысл эпика | Основные work packages |
|---|---|---|
| E1. Baseline and Governance | Фиксация правил и границ MVP | Terminology, Contract Policy, Delivery Governance |
| E2. Core Foundation | Технический каркас системы | Backend Runtime, Migration Foundation, Frontend Shell, Frontend Integration |
| E3. API and Reference CRUD Baseline | Эталонный сквозной CRUD | Reference Model, Backend CRUD, Frontend CRUD, Contract Freeze A |
| E4. Organization Structure | Оргструктура клиента | Data Model, Backend Services, Frontend Workspace, Acceptance Pass |
| E5. Positions and Staffing | Должности и сотрудники | Positions Backend/UI, Employees Backend/UI, Contract Freeze B |
| E6. Accounts and Role Assignment | Доступы и роли | Accounts Backend, Role Assignment Backend, Access UI, Acceptance Pass |
| E7. Onboarding Runs and Process Visibility | Наблюдаемость процесса | Run Model, Run Backend, Runs UI, Contract Freeze C |
| E8. Bootstrap Orchestration and Wizard | Главный MVP-сценарий | Command Contract, Orchestration Backend, Wizard Model, Wizard UI, Contract Freeze D |
| E9. Hardening, Pilot Readiness and Stabilization | Подготовка к пилоту | Backend Hardening, Frontend Hardening, Smoke Suite, Pilot Checkpoint |

---

## 22. Acceptance criteria для документа

Delivery Board / Work Breakdown v1 считается достаточным, если:

- определены верхнеуровневые эпики;
- для каждого эпика выделены work packages;
- зависимости между пакетами прозрачны;
- зафиксировано, что может идти параллельно, а что нет;
- определены deliverables и definition of done на уровне work package;
- зафиксированы checkpoint-ы и demo-логика;
- board можно уже переносить в инструмент управления задачами.

---

## 23. Практический вывод

После фиксации этого документа проект получает уже почти полноценный execution-layer:

- есть архитектура;
- есть API baseline;
- есть backend и frontend delivery plans;
- есть implementation sequence;
- есть work breakdown и delivery board.

Следующий наиболее практичный шаг — сделать один из двух документов:

1. **Iteration Plan for MVP Sprint 1–3** — если нужно перейти к ближайшим рабочим итерациям;
2. **Frontend Screen Map + Navigation Model** — если нужно детальнее зафиксировать пользовательский слой перед началом UI-реализации.

Если цель — быстрее переходить к реальному исполнению, то логичнее следующим делать именно **Iteration Plan for MVP Sprint 1–3**.