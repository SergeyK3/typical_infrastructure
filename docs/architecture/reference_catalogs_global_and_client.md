# Справочники: глобальный каталог и данные организации (тенант)

Здесь описано, как в кодовой базе разделены **общесистемные справочники** и **данные конкретной организации**, и где это смотреть в реализации.

## 1. Есть ли отдельный «оргдокумент» только про это?

**Отдельного** пользовательского руководства только про это разделение **нет**. Схему можно **посмотреть** здесь и в перечисленных местах:

| Где | Что даёт |
|-----|----------|
| **Этот файл** | Сводка: глобальное vs клиент, поля, статус реализации. |
| [`app/models.py`](../../app/models.py) | Определения в коде: докстринги классов `OrgUnit`, `Position`, `PositionCatalog`, `KpiTemplate`, `PositionRegulation`, `ClientPositionRegulation`. |
| [`README.md`](../../README.md) | Запуск приложения и ссылка на **Swagger**: `/docs` — все HTTP-эндпоинты в стиле **REST**, в том числе глобальные регламенты `/api/regulations`. |
| [`docs/specs/документ_№_13.md`](../specs/документ_№_13.md), [`документ_№_15.md`](../specs/документ_№_15.md), [`концептуальная_модель_данных_и_erd_типовая_инфраструктура_b_2_b.md`](концептуальная_модель_данных_и_erd_типовая_инфраструктура_b_2_b.md) | Более ранние концептуальные ТЗ (global / client, роли); не обновляются под каждое новое поле в БД. |

## 2. Глобальные (платформенные) справочники

Строки **без** привязки к `client_id` — один реестр на всё развёртывание:

- **`position_catalog`** — типовые коды/наименования должностей (`PositionCatalog`).
- **`kpi_templates`** — шаблоны KPI (`KpiTemplate`); необязательное поле **`position_code`** — привязка к типовой должности (`position_catalog`). Общие метрики без должности: `position_code` пустой. Список: `GET /api/kpi-templates?dept_type_code=…&position_code=…`, коды отделений: `GET /api/kpi-templates/department-type-codes`; должности с **`primary_dept_type_code`**: `GET /api/regulations/positions/list`.
- **`position_regulations`** (и связанные `regulation_kpis`, `regulation_instructions`) — **глобальные** регламенты должностей (`PositionRegulation`, …).
- **`template_org_units`** — типовая оргструктура в БД по `template_code` (если для шаблона есть строки, они подставляются вместо встроенного списка из `app/org_structures.py` — см. `app/template_org_resolve.py`).

**Интерфейс (глобальное):** хаб **`/global`** и страницы **`/global/template-org`**, **`/global/positions`**, **`/global/kpi`**; регламенты — **`/regulations`**. API: **`/api/template-org-units`**, **`/api/position-catalog`** (в т.ч. POST/PATCH/DELETE), **`/api/kpi-templates`**, **`/api/regulations`**.

## 3. Данные организации (операционные, по `client_id`)

Всё с полем **`client_id`**:

- **`org_units`** — подразделения/секции; могут появиться из **типового шаблона** в коде (`app/org_structures.py`), но записи в БД принадлежат организации.
- **`positions`** — штатные должности; при необходимости ссылаются на глобальный каталог через **`position_catalog_code`**.
- **`employees`**, **`accounts`** и т.д.

**Интерфейс:** рабочее пространство **`/client/{client_id}`** — в сайдбаре блок **«Справочники организации»**: подразделения, должности, регламенты и KPI организации, сотрудники, аккаунты.

## 4. «Скопировали один раз — дальше сами» — флаги и происхождение

Политика: после развёртывания или копии **нет автоматической обратной синхронизации** с глобальным шаблоном/каталогом; глобальная сторона остаётся **историческим контекстом**, если заполнена ссылка.

| Механизм | Таблица / модель | Смысл |
|----------|------------------|--------|
| **`catalog_source_code`** | `OrgUnit` | Код узла в **шаблоне** на момент создания записи (аудит). Переименование «Бухгалтерия» → «Отдел финансирования» меняет **ваше** `name` (и при необходимости `code`); файл шаблона в репозитории не меняется. |
| **`is_detached`** | `OrgUnit`, `Position` | `true` (по умолчанию): нет авто-подтягивания изменений из глобального шаблона / `position_catalog` в эту строку. |
| **`position_catalog_code`** | `Position` | Необязательная связь с **`position_catalog`**, если должность выведена из глобального справочника. |
| **`global_regulation_code`** + **`is_detached`** | `ClientPositionRegulation` | **Клиентская** копия регламента; **`global_regulation_code`** — код глобального `regulation_code` на момент копирования. REST: **`/api/client-regulations`**, **`POST .../copy-from-global`**. |

## 5. Статус в коде (кратко)

- **Сделано:** поля и миграции для `OrgUnit` / `Position`; таблицы `ClientPositionRegulation`, `client_regulation_kpis`, `client_regulation_instructions`; в onboarding и `deploy-template` выставляются происхождение и `is_detached` где уместно; поиск по глобальному реестру регламентов (`GET /api/regulations?search=...`) и страница `/regulations`.
- **REST для копий у организации:**
  - **`POST /api/client-regulations/copy-from-global`** — копия глобального регламента (+ KPI и инструкции) в реестр клиента; далее **`GET/PATCH/DELETE /api/client-regulations/...`**, список **`GET /api/client-regulations?client_id=`**.
  - **`POST /api/positions/from-catalog`** — создать штатную должность из глобального `position_catalog`.
  - **`POST /api/org-units/from-template-node`** — добавить одно подразделение по узлу типового шаблона (родитель по шаблону должен уже существовать у клиента).
- **UI:** слева вверху — блок **«Глобальные справочники»** (ссылки на `/global`, типовую оргструктуру, каталог должностей, KPI, `/regulations`); снизу — **«Справочники организации»** (подразделения, должности, регламенты и KPI этой организации и т.д.). На `/client/{id}` — вкладка **«Регламенты и KPI»**: копирование из глобального реестра, CRUD клиентских карточек.

## 6. Как «посмотреть» в работающем приложении

1. Запустить сервер (см. корневой `README.md`).
2. Открыть **`/docs`** — в том числе **`/api/template-org-units`**, **`/api/kpi-templates`**, расширенный **`/api/position-catalog`**, **`GET /api/regulations`**, **`/api/client-regulations`**, **`POST /api/client-regulations/copy-from-global`**, **`POST /api/positions/from-catalog`**, **`POST /api/org-units/from-template-node`**, **`GET /api/org-units?client_id=...`**, **`GET /api/positions?client_id=...`**.
3. Читать исходники **`app/models.py`**, **`app/template_org_resolve.py`**, **`app/routers/template_org_units.py`**, **`app/routers/kpi_templates.py`**, **`app/routers/position_catalog.py`**, **`app/routers/client_regulations.py`**, **`app/routers/positions.py`**, **`app/routers/org_units.py`**.
