# HR Domain Glossary — Словарь предметной области кадрового контура

| Поле | Значение |
|------|----------|
| **Тип документа** | Architecture Reference (не ADR, не Roadmap) |
| **Дата** | 2026-06-30 |
| **Статус** | Active |
| **Основание** | [ADR-049](../adr/ADR-049-administrative-roles-and-responsibility-model.md), [ADR-050](../adr/ADR-050-personnel-lifecycle-architecture.md), [ADR-051](../adr/ADR-051-personnel-order-workflow-architecture.md) |
| **Governance** | [ARCHITECTURE_GOVERNANCE.md](../ARCHITECTURE_GOVERNANCE.md) |
| **Область действия** | Терминология кадрового контура платформы «Типовая инфраструктура» |

---

## 1. Назначение документа

Документ является **единым словарём терминов** кадрового контура. Любой новый ADR, проект реализации (PROJ-*), API, UI, тест-кейс и код **должны использовать определения отсюда**.

**Документ не принимает новых архитектурных решений.** Он только фиксирует терминологию, уже принятую в Accepted ADR.

**Приоритет при расхождении:** Accepted ADR (ADR-049 → ADR-050 → ADR-051) имеют приоритет над данным словарём. Словарь обновляется при изменении ADR, а не наоборот.

**Рекомендация для задач Cursor:** объявить этот документ **обязательным источником терминологии** для всех последующих задач реализации кадрового контура — это снижает «расползание» понятий между кодом, ADR и UI.

### Каноническая цепочка (термины-соседи)

```text
Person → Employee → Employment → Personal File → Orders → Documents → Archive
         ↑ Aggregate Root                    Order Lifecycle: Draft → … → Effective
         └────────────► Account → Access   (org-tech, ADR-049)
```

---

## 2. Формат записи словаря

Каждый термин описан таблицей с полями:

| Поле | Назначение |
|------|------------|
| **Термин** | Каноническое имя (English identifier в коде и ADR) |
| **Краткое определение** | Одна строка |
| **Подробное описание** | Семантика, границы ответственности |
| **Источник (ADR)** | Разделы ADR-049 / ADR-050 / ADR-051 |
| **Связанные термины** | Соседние понятия домена |
| **Синонимы** | Допустимые альтернативы (если есть) |
| **Недопустимые употребления** | Типичные ошибки именования |
| **Примечания** | Cross-ref, MVP / future |

---

## 3. Словарь терминов

### Person

| | |
|---|---|
| **Термин** | Person |
| **Краткое определение** | Identity aggregate — устойчивая идентичность человека в рамках Client. |
| **Подробное описание** | Якорь биографических и персональных данных, не зависящих от конкретного периода работы: ФИО (история через Events), дата рождения, документы личности, образование, семейное положение, контакты. Не удаляется при увольнении. Может существовать до Employee (Candidate, pre-hire). Связь с кадровым контуром — через `Employee.person_id`. Person — **не** Aggregate Root кадрового lifecycle. |
| **Источник (ADR)** | ADR-050 §3.1, §4.3; ADR-049 §1.2 |
| **Связанные термины** | Identity, Employee, Candidate, Document, Personnel Event |
| **Синонимы** | Физическое лицо *(допустимо в русскоязычной документации)* |
| **Недопустимые употребления** | «Сотрудник»; «Person = Employee»; хранение текущей должности / подразделения на Person |
| **Примечания** | [ADR-050 §3.1](../adr/ADR-050-personnel-lifecycle-architecture.md); UI entry — через карточку Employee |

---

### Employee

| | |
|---|---|
| **Термин** | Employee |
| **Краткое определение** | HR Aggregate Root — постоянная кадровая сущность Client. |
| **Подробное описание** | Организационная якорная запись, связь Person с Client. Создаётся **один раз** для пары Person + Client; **не пересоздаётся** при Rehire. Содержит кадровый агрегат: Employment, Personal File, Personnel Events, Orders, Documents, Archive. Ответственность: `person_id`, табельный номер (`employee_code`), агрегированный статус реестра, read-only индикатор Account. Единая точка mutating access для кадрового контура (роль `hr`). |
| **Источник (ADR)** | ADR-050 §3.2, §4.2, INV-2, INV-17; ADR-049 §1.2, §7.3 |
| **Связанные термины** | Person, Employment, Personal File, Aggregate Root, Archive, Rehire |
| **Синонимы** | Сотрудник организации *(RU)* |
| **Недопустимые употребления** | «Текущая должность»; «Текущее подразделение»; «Статус занятости» как поле Employee без projection; «Новый Employee при rehire» |
| **Примечания** | [ADR-050 §4.2](../adr/ADR-050-personnel-lifecycle-architecture.md); lifecycle: `draft` → `active` → `archived` → `reactivated` |

---

### Employment

| | |
|---|---|
| **Термин** | Employment |
| **Краткое определение** | Конкретный период работы Employee в организации. |
| **Подробное описание** | Один объект = один период от HIRE / REHIRE до TERMINATION или текущего момента. Ответственность: `date_from`, `date_to`, тип занятости, Organization Unit, Position, ставка (FTE), руководитель, статус периода (`active` / `on_leave` / `suspended` / `terminated`). Lifecycle-изменения **только** через Personnel Events, не PATCH. Закрытый (`terminated`) период — immutable. |
| **Источник (ADR)** | ADR-050 §3.3, INV-3, INV-4, INV-12 |
| **Связанные термины** | Employee, Current Employment, Employment History, Personnel Event, Order, Position, Organization Unit |
| **Синонимы** | Период работы *(RU)* |
| **Недопустимые употребления** | «Employment = Employee»; «Employment = Position»; reopen terminated Employment при Rehire; PATCH должности / подразделения |
| **Примечания** | [ADR-050 §3.3](../adr/ADR-050-personnel-lifecycle-architecture.md); org_unit / position — projection из Events |

---

### Current Employment

| | |
|---|---|
| **Термин** | Current Employment |
| **Краткое определение** | Проекция активного периода работы Employee на текущую дату. |
| **Подробное описание** | Read-model: Employment со статусом `active` (или `on_leave` / `suspended` по политике отображения) без `date_to` или с `date_to` в будущем. Используется в реестре и карточке для «текущих» org_unit, position, FTE. Не отдельная сущность — derived view над Employment + Events. |
| **Источник (ADR)** | ADR-050 §3.3, §8.1, P-13; roadmap PROJ-EMPLOYMENT |
| **Связанные термины** | Employment, Projection, Employee, Personnel Event |
| **Синонимы** | Текущий период работы *(RU, контекстно)* |
| **Недопустимые употребления** | Хранение current position на Employee как authoritative source; смешение с Employment History |
| **Примечания** | При нескольких open periods — явная политика выбора (OQ, ADR-056) |

---

### Employment History

| | |
|---|---|
| **Термин** | Employment History |
| **Краткое определение** | Совокупность всех Employment одного Employee, включая terminated. |
| **Подробное описание** | Append-only набор периодов работы. Отображается в Personal File (раздел «История работы») и timeline. При Rehire добавляется новый Employment; старые периоды не изменяются. |
| **Источник (ADR)** | ADR-050 §3.3, INV-3, INV-4, §9.2 |
| **Связанные термины** | Employment, Rehire, Personal File, Timeline, Archive |
| **Синонимы** | История периодов работы *(RU)* |
| **Недопустимые употребления** | «История = Current Employment»; удаление terminated periods |
| **Примечания** | [ADR-050 §8.2](../adr/ADR-050-personnel-lifecycle-architecture.md) |

---

### Personal File

| | |
|---|---|
| **Термин** | Personal File |
| **Краткое определение** | Content Hub — структурированное кадровое дело внутри агрегата Employee. |
| **Подробное описание** | Центральная модель кадрового дела: архитектурные разделы (фото, персональные сведения, образование, хронология, приказы и т.д.), ссылки на Orders и Documents, Timeline Personnel Events. **Один** Personal File на Employee; сохраняется между Employment; не удаляется. Lifecycle: `open` ↔ `read_only` (Archive) ↔ `open` (Rehire). |
| **Источник (ADR)** | ADR-050 §3.4, §9, INV-5, INV-16 |
| **Связанные термины** | Employee, Content Hub, Timeline, Document, Order, Person |
| **Синонимы** | Личный листок, кадровое дело *(RU)* |
| **Недопустимые употребления** | «Personal File = Employee»; «Personal File без Employee»; independent aggregate root |
| **Примечания** | [ADR-050 §9](../adr/ADR-050-personnel-lifecycle-architecture.md); UI rules — отдельный проект |

---

### Personnel Event

| | |
|---|---|
| **Термин** | Personnel Event |
| **Краткое определение** | Append-only факт кадрового изменения в истории Employee. |
| **Подробное описание** | Единственный штатный механизм lifecycle-мутаций Employment и агрегированного статуса Employee (INV-12). Каталог: `HIRE`, `REHIRE`, `TRANSFER`, `TERMINATION`, `LEAVE_START`, … Lifecycle Event, изменяющий Employment, **требует Order** (INV-11). Создаётся при переходе Order в **Effective** (ADR-051). Обновляет Employment projection и Personal File Timeline. |
| **Источник (ADR)** | ADR-050 §3.6, INV-6, INV-11, INV-12; ADR-051 §5 |
| **Связанные термины** | Order, Effective, Employment, Timeline, Append-only |
| **Синонимы** | Кадровое событие *(RU)*; Event *(сокращение в контексте HR)* |
| **Недопустимые употребления** | «Event = Order»; «Event = Employment»; lifecycle PATCH вместо Event |
| **Примечания** | [ADR-050 §10.2](../adr/ADR-050-personnel-lifecycle-architecture.md) — каталог events |

---

### Order

| | |
|---|---|
| **Термин** | Order |
| **Краткое определение** | Юридическое основание кадрового решения (сущность, не файл). |
| **Подробное описание** | Регистрация приказа: номер, дата, тип (`order_type`), workflow-статус, `effective_date`, связь с Employee (и опционально Employment). Слои: Metadata, Workflow, Legal link (Personnel Event после Effective), Documents. Permanent record; не удаляется. Принадлежит агрегату Employee (INV-17). |
| **Источник (ADR)** | ADR-050 §3.5, INV-8, INV-11; ADR-051 §3 |
| **Связанные термины** | Order Lifecycle, Personnel Event, Document, Effective, Signed, Compensating Order |
| **Синонимы** | Приказ, кадровый приказ *(RU)* |
| **Недопустимые употребления** | «Order = PDF file»; «Order = Personnel Event»; PATCH Employment «по приказу» без Effective |
| **Примечания** | [ADR-051 §3.2](../adr/ADR-051-personnel-order-workflow-architecture.md) — каталог order_type |

---

### Order Lifecycle

| | |
|---|---|
| **Термин** | Order Lifecycle |
| **Краткое определение** | Последовательность статусов и переходов Order от создания до архивации. |
| **Подробное описание** | Каноническая цепочка: **Draft → Review → Approved → Signed → Effective → Archived**. Дополнительно: **Void** (terminal, только до Signed). Mutable zone: Draft…Approved. Immutable zone: Signed → Effective → Archived. Review опционален по `order_type`. `pending_signature` (ADR-050) maps to **Approved**. |
| **Источник (ADR)** | ADR-051 §4; ADR-050 §3.5 (упрощённая модель superseded) |
| **Связанные термины** | Draft, Review, Approved, Signed, Effective, Void, Archived, Compensating Order |
| **Синонимы** | Workflow приказа *(RU)* |
| **Недопустимые употребления** | Пропуск Signed перед Effective; Void после Signed |
| **Примечания** | [ADR-051 §4.2](../adr/ADR-051-personnel-order-workflow-architecture.md) — state diagram |

---

### Document

| | |
|---|---|
| **Термин** | Document |
| **Краткое определение** | Файловый артефакт и первичное доказательство кадрового учёта. |
| **Подробное описание** | Метаданные, MIME/format, storage ref, связь с Order / Personal File / Person / Personnel Event. Роли в контексте Order: `draft_word`, `generated_pdf`, `signed_pdf`, `signed_scan`, `esign_evidence`. Permanent; **append-only** — новая информация = новая version. Final versions immutable. |
| **Источник (ADR)** | ADR-050 §3.6, INV-7; ADR-051 §7 |
| **Связанные термины** | Document Version, Order, Canonical Document, Append-only, Immutable |
| **Синонимы** | Кадровый документ *(RU)* |
| **Недопустимые употребления** | «Document = Order»; overwrite final version; DELETE как штатная операция |
| **Примечания** | Physical storage — ADR-052 (planned) |

---

### Document Version

| | |
|---|---|
| **Термин** | Document Version |
| **Краткое определение** | Одна неизменяемая ревизия Document в append-only lineage. |
| **Подробное описание** | Новая правка текста в Draft Order → новая version `draft_word`, старые помечаются `superseded`. Final / signed versions: `id`, `version`, `content_hash`, `created_at`, storage ref — immutable. После Signed Order — только новые Document через Compensating Order. |
| **Источник (ADR)** | ADR-050 §3.6, INV-7; ADR-051 §7.2 |
| **Связанные термины** | Document, Append-only, Immutable, Order |
| **Синонимы** | Версия документа *(RU)* |
| **Недопустимые употребления** | «Version = отдельный Order»; in-place UPDATE content_hash final version |
| **Примечания** | [ADR-051 §7.2](../adr/ADR-051-personnel-order-workflow-architecture.md) — version lineage diagram |

---

### Archive

| | |
|---|---|
| **Термин** | Archive |
| **Краткое определение** | Логический read-only режим завершённых кадровых записей. |
| **Подробное описание** | **Не** DELETE и **не** отдельная «корзина». Logical flag на Employee (`archived`), Employment (terminated + archived), Personal File (`read_only`). Наступает после TERMINATION; снимается при REHIRE. Архивные Employment, Events, signed Orders, final Documents не изменяются. Block Account — org-tech (ADR-049), не Archive. |
| **Источник (ADR)** | ADR-050 §3.7, INV-9, INV-10; ADR-049 OQ-14 |
| **Связанные термины** | Read-only Archive, Employee, Termination, Rehire, Account |
| **Синонимы** | Кадровый архив *(RU)* |
| **Недопустимые употребления** | «Archive = Delete»; «Archive = block Account»; hard delete personnel history |
| **Примечания** | [ADR-050 §3.7](../adr/ADR-050-personnel-lifecycle-architecture.md) |

---

### Rehire

| | |
|---|---|
| **Термин** | Rehire |
| **Краткое определение** | Повторный приём — reactivation того же Employee с новым Employment. |
| **Подробное описание** | Personnel Event `REHIRE` + Order (`order_type: rehire`). **Не** создаёт новый Employee (INV-2). **Создаёт** новый Employment (INV-4). Reopens Personal File (`read_only` → `open`). Тот же Aggregate Root, та же Person, тот же Personal File (INV-5). |
| **Источник (ADR)** | ADR-050 §4.2, §8.2, INV-2, INV-4, INV-5; ADR-051 §3.2 |
| **Связанные термины** | Employee, Employment, Archive, Personnel Event, Order |
| **Синонимы** | Повторный приём *(RU)* |
| **Недопустимые употребления** | «Rehire = новый Employee»; reopen old terminated Employment |
| **Примечания** | [ADR-050 §8.4](../adr/ADR-050-personnel-lifecycle-architecture.md) — state diagram Rehire |

---

### Candidate

| | |
|---|---|
| **Термин** | Candidate |
| **Краткое определение** | Опциональная pre-hire сущность до HIRE. |
| **Подробное описание** | Данные кандидата, статус отбора, связь с будущим Person. Employee и Personal File **не создаются** до HIRE. При HIRE: Person + Employee создаются, Candidate закрывается. Phase E (PROJ-CANDIDATE). |
| **Источник (ADR)** | ADR-050 §3.8, §8.1 |
| **Связанные термины** | Person, Employee, HIRE, Lifecycle |
| **Синонимы** | Кандидат *(RU)* |
| **Недопустимые употребления** | «Candidate = Employee»; полноценный кадровый учёт до HIRE |
| **Примечания** | Будущий ADR-057 |

---

### Account

| | |
|---|---|
| **Термин** | Account |
| **Краткое определение** | Учётная запись — средство технического доступа в систему (org-tech). |
| **Подробное описание** | Не кадровая сущность. Связь Employee → 0..1 Account (read-only для HR). Клиентский Account обязан иметь `employee_id`. Создание, block/unblock, reset password — роль `admin` (ADR-049). Кадровый контур **не создаёт** Account (INV-13). |
| **Источник (ADR)** | ADR-049 §1.2, §2.2, §7.5; ADR-050 INV-13, §4.4 |
| **Связанные термины** | Access, Employee, Role, Client |
| **Синонимы** | Учётная запись *(RU)* |
| **Недопустимые употребления** | «Account = Employee»; «HR создаёт пользователей»; смешение `account.status` с employment status |
| **Примечания** | [ADR-049 §7.5](../adr/ADR-049-administrative-roles-and-responsibility-model.md) |

---

### Access

| | |
|---|---|
| **Термин** | Access |
| **Краткое определение** | Назначенные права доступа через role codes на Account. |
| **Подробное описание** | Цепочка ADR-049: Account → Access (Role codes). Каталог role codes платформенный (`admin`, `hr`, `manager`, `employee`, …). Назначение — org-tech контур (`admin`). RBAC engine — док. №15. |
| **Источник (ADR)** | ADR-049 §1.2, §2.1, §7; ADR-050 INV-13 |
| **Связанные термины** | Account, Role, RBAC, Employee |
| **Синонимы** | Доступ, права доступа *(RU)* |
| **Недопустимые употребления** | «Access = кадровые полномочия без role code»; новые role codes клиентом |
| **Примечания** | Workflow приказов — permission layer, не новые codes (ADR-051 §6) |

---

### Client

| | |
|---|---|
| **Термин** | Client |
| **Краткое определение** | Tenant — организация-клиент платформы (мультитенантный scope). |
| **Подробное описание** | Граница данных: Person, Employee, справочники, Orders нумеруются в scope Client. Три контура (platform, org-tech, HR) работают на уровне Client. Employee уникален per (Person, Client). |
| **Источник (ADR)** | ADR-049 §1.3, §3; ADR-050 INV-2 |
| **Связанные термины** | Employee, Person, Organization Unit, Client |
| **Синонимы** | Клиент, организация *(RU, контекст tenant)* |
| **Недопустимые употребления** | «Client = Employee»; смешение platform scope и client scope |
| **Примечания** | Platform onboarding — ADR-049 §3.1 |

---

### Organization Unit

| | |
|---|---|
| **Термин** | Organization Unit |
| **Краткое определение** | Подразделение организации — элемент оргструктуры Client. |
| **Подробное описание** | Справочник org-tech / HR. Назначение на Employment — через Personnel Events (projection). Scope делегирования уполномоченного ОК (`hr`, org_unit). Не identity и не period сам по себе. |
| **Источник (ADR)** | ADR-049 §3.2, OQ-1; ADR-050 §3.3 |
| **Связанные термины** | Employment, Position, Employee, Client |
| **Синонимы** | Org unit, подразделение *(RU)*; `org_unit` *(код)* |
| **Недопустимые употребления** | «Org unit на Person»; PATCH org_unit без Event |
| **Примечания** | Локальный справочник — `admin`; кадровое назначение — `hr` через Order |

---

### Position

| | |
|---|---|
| **Термин** | Position |
| **Краткое определение** | Должность — элемент справочника Client, назначаемая на Employment. |
| **Подробное описание** | Справочная сущность (должностная позиция). Текущая должность сотрудника — **projection** Current Employment после Events (`TRANSFER`, `POSITION_CHANGE`, `PROMOTION`), не поле Person / authoritative PATCH Employee. |
| **Источник (ADR)** | ADR-050 §3.3; ADR-049 (локальные справочники) |
| **Связанные термины** | Employment, Organization Unit, Personnel Event, Role |
| **Синонимы** | Должность *(RU)*; `position_id` *(код)* |
| **Недопустимые употребления** | «Position = Role»; «Position = Employee»; должность как атрибут Person |
| **Примечания** | [reference_catalogs](../reference_catalogs_global_and_client.md) |

---

### Role

| | |
|---|---|
| **Термин** | Role |
| **Краткое определение** | Системная роль доступа (role code), назначаемая на Account. |
| **Подробное описание** | В ADR-049: **архитектурная персона** (HR руководитель, локальный admin) **мапится** на **role code** (`hr`, `admin`, `manager`, …) без изменения каталога codes. Role ≠ Position. Workflow приказов использует architectural personas + permission layer (ADR-051 §6). |
| **Источник (ADR)** | ADR-049 §2.1, §3; ADR-051 §6 |
| **Связанные термины** | Access, Account, Position, RBAC |
| **Синонимы** | Role code, системная роль *(RU)* |
| **Недопустимые употребления** | «Role = должность»; «Role = Employee»; новые role codes для bilingual / order workflow |
| **Примечания** | Seed codes: `app/seed.py` (as-is MVP) |

---

### Identity

| | |
|---|---|
| **Термин** | Identity |
| **Краткое определение** | Устойчивые биографические и персональные данные человека (domain Person). |
| **Подробное описание** | Identity aggregate владелец — **Person**. Отделён от организационного контекста (Employee) и периода работы (Employment). INV-1: identity persistence — Person не удаляется. |
| **Источник (ADR)** | ADR-050 §3.1, §4.3, INV-1; ADR-049 §1.2 |
| **Связанные термины** | Person, Employee, Document |
| **Синонимы** | Идентичность, персональная идентичность *(RU)* |
| **Недопустимые употребления** | «Identity = Employment»; «Identity = Account login» |
| **Примечания** | Anonymization — отдельная compliance-политика |

---

### Aggregate Root

| | |
|---|---|
| **Термин** | Aggregate Root |
| **Краткое определение** | Корневая сущность агрегата — единая точка consistency boundary. |
| **Подробное описание** | В кадровом контуре: **Employee** — единственный Aggregate Root (INV-17). Employment, Personal File, Personnel Events, Orders, Documents, Archive не мутируются вне контекста Employee. **Person** — отдельный identity aggregate. **Account → Access** — org-tech aggregate (ADR-049). |
| **Источник (ADR)** | ADR-050 §4, INV-17; ADR-049 §4.4 |
| **Связанные термины** | Employee, Person, Account |
| **Синонимы** | Корень агрегата *(RU)* |
| **Недопустимые употребления** | «Personal File as aggregate root»; «Order без Employee» |
| **Примечания** | [ADR-050 §4.6](../adr/ADR-050-personnel-lifecycle-architecture.md) — diagram |

---

### Content Hub

| | |
|---|---|
| **Термин** | Content Hub |
| **Краткое определение** | Архитектурная роль Personal File — центр контента кадрового дела. |
| **Подробное описание** | Personal File агрегирует разделы, Timeline, ссылки на Orders/Documents. Не workflow engine и не storage. Entry point кадрового контента вместе с карточкой Employee (INV-16). |
| **Источник (ADR)** | ADR-050 §3.4, §9.1 |
| **Связанные термины** | Personal File, Timeline, Employee |
| **Синонимы** | Контентный hub *(RU)* |
| **Недопустимые употребления** | «Hub = blob storage»; «Hub = Order workflow» |
| **Примечания** | Термин архитектурный, не имя таблицы БД |

---

### Projection

| | |
|---|---|
| **Термин** | Projection |
| **Краткое определение** | Read-model, выведенная из Events / Employment, не authoritative PATCH. |
| **Подробное описание** | Поля `org_unit_id`, `position_id`, employment status на Employee / Current Employment — проекции после Effective Event (P-13). Employment projection обновляется Personnel Event, не Order напрямую и не PATCH при Mark Effective. |
| **Источник (ADR)** | ADR-050 P-13, INV-12; ADR-051 §5.4, LR-4 |
| **Связанные термины** | Personnel Event, Employment, Effective, Employee |
| **Синонимы** | Проекция, read-model *(RU)* |
| **Недопустимые употребления** | PATCH projection как lifecycle; Order Signed меняет Employment без Event |
| **Примечания** | UI/API должны читать projections, не mute authoritative store |

---

### Timeline

| | |
|---|---|
| **Термин** | Timeline |
| **Краткое определение** | Хронологическое представление Personnel Events в Personal File. |
| **Подробное описание** | Read-model поверх append-only Events: кадровая хронология, раздел «Приказы и основания». Пополняется при каждом Effective Event. Не мутируется retroactively. |
| **Источник (ADR)** | ADR-050 §3.4, §9; ADR-051 §5.1 |
| **Связанные термины** | Personal File, Personnel Event, Order |
| **Синонимы** | Кадровая хронология *(RU)* |
| **Недопустимые употребления** | «Timeline = Order workflow status»; редактирование прошлых записей |
| **Примечания** | PROJ-EVENTS, PROJ-PERSONAL-FILE |

---

### Lifecycle

| | |
|---|---|
| **Термин** | Lifecycle |
| **Краткое определение** | Параллельные оси состояния сущностей кадрового контура во времени. |
| **Подробное описание** | **Не** одно поле `status`. Оси: Person, Candidate (optional), Employee, Employment, Personal File, Account (ADR-049), Order. Фазы: Hire, Active, Transfer, Leave, Termination, Archive, Rehire (ADR-050 §8). Lifecycle-изменения — Events + Orders, не PATCH (INV-12). |
| **Источник (ADR)** | ADR-050 §8; ADR-051 §4 |
| **Связанные термины** | Personnel Event, Order Lifecycle, Employment, Archive |
| **Синонимы** | Жизненный цикл *(RU)* |
| **Недопустимые употребления** | Единый «статус сотрудника» без указания оси (Employee vs Employment vs Order) |
| **Примечания** | [ADR-050 §8.1](../adr/ADR-050-personnel-lifecycle-architecture.md) — таблица осей |

---

### Compensating Order

| | |
|---|---|
| **Термин** | Compensating Order |
| **Краткое определение** | Приказ-компенсация для отмены / исправления после Signed. |
| **Подробное описание** | Единственный штатный способ отмены Signed / Effective Order (INV-8, LR-3). Типы: `order_cancel`, `amendment`. Порождает compensating Personnel Event (`ORDER_CANCEL` или контекстный). **Запрещён** Void / UPDATE signed Order. |
| **Источник (ADR)** | ADR-050 §3.5, INV-8; ADR-051 §4.4, §3.2 |
| **Связанные термины** | Order, Void, Signed, Effective, Personnel Event |
| **Синонимы** | Компенсирующий приказ *(RU)* |
| **Недопустимые употребления** | «Delete order»; «Void signed order»; PATCH signed metadata |
| **Примечания** | [ADR-051 §4.4](../adr/ADR-051-personnel-order-workflow-architecture.md) |

---

### Effective

| | |
|---|---|
| **Термин** | Effective |
| **Краткое определение** | Статус Order: вступил в силу; создан Personnel Event. |
| **Подробное описание** | Переход Signed → Effective (на `effective_date` или manual/scheduled trigger). **Единственная** штатная точка создания lifecycle Personnel Event (OW-3). Обновляет Employment projection и Timeline. **Effective ≠ PATCH Employment** (LR-4, OW-19). Immutable после входа. |
| **Источник (ADR)** | ADR-051 §4.1, §5.3, LR-4, OW-3; ADR-050 INV-11 |
| **Связанные термины** | Signed, Personnel Event, Order, Projection |
| **Синонимы** | Вступил в силу *(RU)*; `Effective` status |
| **Недопустимые употребления** | «Effective = Signed»; Mark Effective как PATCH; Event до Signed |
| **Примечания** | OQ-51-1: cron vs manual confirm |

---

### Signed

| | |
|---|---|
| **Термин** | Signed |
| **Краткое определение** | Статус Order: подписан; начало immutable zone. |
| **Подробное описание** | Переход Approved → Signed (Manual Signature или Electronic Signature adapter). После Signed Order **immutable** (INV-8, LR-1). Требует canonical documents per `required_locales`. Ещё **не** создаёт Personnel Event — только после Effective. |
| **Источник (ADR)** | ADR-051 §4.1, LR-1; ADR-050 INV-8 |
| **Связанные термины** | Approved, Effective, Immutable, Manual Signature, Electronic Signature, Canonical Document |
| **Синонимы** | Подписан *(RU)* |
| **Недопустимые употребления** | «Signed = Effective»; редактирование Signed Order; Void из Signed |
| **Примечания** | OW-2: immutable from Signed |

---

### Approved

| | |
|---|---|
| **Термин** | Approved |
| **Краткое определение** | Статус Order: согласован; готов к подписанию. |
| **Подробное описание** | Metadata locked; Word → final `generated_pdf`. Ожидает подписи (`pending_signature` ADR-050 → Approved). Void допустим. E-sign failure возвращает остаётся Approved (OW-16). |
| **Источник (ADR)** | ADR-051 §4.1; ADR-050 §3.5 |
| **Связанные термины** | Review, Signed, Draft, Void |
| **Синонимы** | Согласован *(RU)*; ожидает подписи *(контекстно)* |
| **Недопустимые употребления** | «Approved = Effective»; редактирование locked metadata без return to Draft |
| **Примечания** | Approve — HR руководитель (ADR-051 §6) |

---

### Draft

| | |
|---|---|
| **Термин** | Draft |
| **Краткое определение** | Статус Order: черновик; полностью редактируемый. |
| **Подробное описание** | Создаётся из карточки Employee. Редактируются metadata и Word (`draft_word`). Submit → Review или Void. Не создаёт Event; не меняет Employment. |
| **Источник (ADR)** | ADR-051 §4.1, §4.3 |
| **Связанные термины** | Review, Order, Document |
| **Синонимы** | Черновик *(RU)* |
| **Недопустимые употребления** | «Draft order уже изменил должность» |
| **Примечания** | Create Draft — HR / уполномоченный ОК |

---

### Review

| | |
|---|---|
| **Термин** | Review |
| **Краткое определение** | Статус Order: на проверке / согласовании. |
| **Подробное описание** | Опциональный этап по `order_type`. Участники: HR, manager (policy). Переходы: → Approved, → Draft (revision), → Void. Ограниченно mutable. |
| **Источник (ADR)** | ADR-051 §4.1, §6.4 |
| **Связанные термины** | Draft, Approved, Order Lifecycle |
| **Синонимы** | На проверке *(RU)* |
| **Недопустимые употребления** | «Review = Approved»; manager создаёт Order |
| **Примечания** | LR-5: Review optional on happy-path |

---

### Void

| | |
|---|---|
| **Термин** | Void |
| **Краткое определение** | Terminal-статус Order: отменён до подписания. |
| **Подробное описание** | Допустим из Draft, Review, Approved (**только до Signed**, LR-2). Не порождает Personnel Event; не оставляет следов в Employment. Из Signed / Effective / Archived — **Void запрещён**. |
| **Источник (ADR)** | ADR-051 §4.1, LR-2 |
| **Связанные термины** | Draft, Approved, Compensating Order, Signed |
| **Синонимы** | Аннулирован (pre-sign) *(RU)* |
| **Недопустимые употребления** | «Void signed order»; «Void = Termination» |
| **Примечания** | Post-Signed cancel → Compensating Order only |

---

### Manual Signature

| | |
|---|---|
| **Термин** | Manual Signature |
| **Краткое определение** | Подписание Approved → Signed вручную с загрузкой signed scan. |
| **Подробное описание** | Phase 1 реализация (ADR-051 §9). HR загружает `signed_scan` (и опционально `signed_pdf`). Подтверждается Canonical Document по policy (OW-21). Тот же переход Approved → Signed, что и e-sign — **не** отдельная lifecycle-ветка. |
| **Источник (ADR)** | ADR-051 §9.0, §9.1, OW-21 |
| **Связанные термины** | Electronic Signature, Signed, Canonical Document, Approved |
| **Синонимы** | Ручная подпись *(RU)*; manual sign |
| **Недопустимые употребления** | «Manual sign создаёт Event»; смешение с e-sign в одном неявном flow |
| **Примечания** | Signer может быть вне системы (director без Account) |

---

### Electronic Signature

| | |
|---|---|
| **Термин** | Electronic Signature |
| **Краткое определение** | Подписание Approved → Signed через ESignAdapter (future). |
| **Подробное описание** | Архитектурная точка расширения (ADR-051 §9). Adapter создаёт `signed_pdf` + `esign_evidence`. Провайдер (НУЦ, DocuSign, …) — вне scope ADR. При failure Order остаётся Approved (OW-16). Phase C+ (PROJ-ORDER-ESIGN). |
| **Источник (ADR)** | ADR-051 §9, §2.2, OW-13…OW-16 |
| **Связанные термины** | Manual Signature, Signed, Document |
| **Синонимы** | E-sign, ЭЦП *(RU, контекстно)* |
| **Недопустимые употребления** | «E-sign = отдельный Order lifecycle»; e-sign меняет Employment без Effective |
| **Примечания** | `esign_enabled` in signer_policy |

---

### required_locales

| | |
|---|---|
| **Термин** | required_locales |
| **Краткое определение** | Список обязательных языков Document для перехода Order в Signed. |
| **Подробное описание** | Поле Order: `required_locales[]` (напр. `["ru","kk"]`) из `signer_policy` клиента (OW-9). Signed требует canonical document **для каждого** required locale (OW-10). Один Order — одно решение; языки — параллельные Document (ML-1, ML-2). |
| **Источник (ADR)** | ADR-051 §8.2, OW-9, OW-10, ML-3 |
| **Связанные термины** | Canonical Document, Order, Document |
| **Синонимы** | Обязательные локали *(RU)* |
| **Недопустимые употребления** | Отдельный Order per locale; разные order_number per language |
| **Примечания** | Modes: `single_locale`, `full_bilingual`, `primary_plus_translation` |

---

### Canonical Document

| | |
|---|---|
| **Термин** | Canonical Document |
| **Краткое определение** | Authoritative immutable Document, подтверждающий подписанный Order. |
| **Подробное описание** | Audit trail: `signed_scan` или `signed_pdf` + `esign_evidence`. Ссылка `Order.canonical_document_id` (per locale). Требуется для каждого `required_locales` entry at Signed (OW-10). |
| **Источник (ADR)** | ADR-051 §7.1, OW-10, OW-21 |
| **Связанные термины** | Document, Signed, required_locales, Manual Signature, Electronic Signature |
| **Синонимы** | Канонический документ *(RU)* |
| **Недопустимые употребления** | `draft_word` as canonical; overwrite canonical |
| **Примечания** | [ADR-051 §7.1](../adr/ADR-051-personnel-order-workflow-architecture.md) |

---

### Append-only

| | |
|---|---|
| **Термин** | Append-only |
| **Краткое определение** | Модель данных: только добавление, без retroactive DELETE / silent UPDATE. |
| **Подробное описание** | Применяется к Personnel Events, Employment history, Document versions (INV-6, INV-7). Новая информация = новая запись / version. Принцип P-2 ADR-050. |
| **Источник (ADR)** | ADR-050 INV-6, INV-7, P-2 |
| **Связанные термины** | Personnel Event, Document Version, Immutable |
| **Синонимы** | Только добавление *(RU)* |
| **Недопустимые употребления** | Hard delete history; in-place edit signed content |
| **Примечания** | Исключения только migration + regulated correction (INV-11) |

---

### Immutable

| | |
|---|---|
| **Термин** | Immutable |
| **Краткое определение** | Запрет изменения после наступления контрольной точки. |
| **Подробное описание** | Signed Order и далее (INV-8); final Document versions; terminated Employment; архивные записи. Изменение — только через новые append-only artifacts (Compensating Order, new Document version before Signed). |
| **Источник (ADR)** | ADR-050 INV-8, §3.3; ADR-051 LR-1, OW-2 |
| **Связанные термины** | Signed, Append-only, Compensating Order |
| **Синонимы** | Неизменяемый *(RU)* |
| **Недопустимые употребления** | UPDATE signed order; edit terminated employment period |
| **Примечания** | Mutable zone Order: Draft…Approved |

---

### Read-only Archive

| | |
|---|---|
| **Термин** | Read-only Archive |
| **Краткое определение** | Режим Archive: просмотр без mutating operations. |
| **Подробное описание** | Employee `archived`, Personal File `read_only`, Employment terminated + immutable. Мутации запрещены кроме REHIRE flow. Не физическое удаление (INV-9). UI: PROJ-ARCHIVE-UI. |
| **Источник (ADR)** | ADR-050 §3.7, INV-9; §8.2 Phase Archive |
| **Связанные термины** | Archive, Employee, Personal File, Termination |
| **Синонимы** | Архив только для чтения *(RU)* |
| **Недопустимые употребления** | «Read-only = deleted»; edit archived Personal File без Rehire |
| **Примечания** | Block Account — отдельный org-tech процесс |

---

## 4. Frequently Confused Terms

| # | Различие | Пояснение |
|---|----------|-----------|
| 1 | **Person ≠ Employee** | Person — identity; Employee — организационный контекст Client. Один Person → один Employee per Client. |
| 2 | **Employee ≠ Employment** | Employee — aggregate root на всю историю; Employment — один период работы. |
| 3 | **Employment ≠ Position** | Position — справочник; Employment / projection несёт назначение на период. |
| 4 | **Order ≠ Personnel Event** | Order — юридическое решение + workflow; Event — append-only факт истории после Effective. |
| 5 | **Personnel Event ≠ Employment** | Event mutates projection; Employment — объект периода, не дубликат Event. |
| 6 | **Order ≠ Document** | Order — сущность metadata; Document — файл / version lineage. |
| 7 | **Archive ≠ Delete** | Archive — logical read-only (INV-9); hard delete personnel history запрещён (INV-10). |
| 8 | **Account ≠ Employee** | Account — org-tech доступ; Employee — кадровая запись (INV-13). |
| 9 | **Role ≠ Position** | Role — role code на Account; Position — должность на Employment. |
| 10 | **Identity ≠ Employment** | Identity (Person) persist; Employment — периоды работы. |
| 11 | **Current Employment ≠ Employment History** | Current — projection сейчас; History — все periods including terminated. |
| 12 | **Signed ≠ Effective** | Signed — immutable подпись; Effective — вступление в силу + создание Event. |
| 13 | **Manual Signature ≠ Electronic Signature** | Оба: Approved → Signed; разные adapters, один lifecycle. |
| 14 | **Document ≠ Document Version** | Document — logical artifact; Version — одна ревизия в lineage. |
| 15 | **Employee ≠ Personal File** | Employee — root; Personal File — content hub 1:1 inside aggregate. |
| 16 | **Rehire ≠ New Employee** | Rehire reactivates same Employee + new Employment (INV-2, INV-4). |
| 17 | **Void ≠ Compensating Order** | Void — только pre-Signed; post-Signed — compensating Order only. |
| 18 | **Projection ≠ Source of truth** | Authoritative changes — Events; projections — derived read-models. |

---

## 5. Deprecated / Avoid — термины, запрещённые или неоднозначные

| Избегать | Использовать вместо | Контекст |
|----------|-------------------|----------|
| «Карточка сотрудника» *(как имя сущности)* | **Employee** или **Personal File** | UI entry point ≠ entity name; карточка — экран, не модель |
| «Статус сотрудника» *(без уточнения оси)* | **Employee status** / **Employment state** / **Order status** | Указать ось lifecycle (§ Lifecycle) |
| «Удалить сотрудника» | **Archive**, **Termination**, **logical archive** | Hard delete запрещён (INV-10) |
| «Создать пользователя» (HR context) | **Create Employee**; Account — **admin** | ADR-049 §2.2 |
| «HR создаёт аккаунты» | **admin создаёт Account** | INV-13 |
| «Пользователь» *(без уточнения)* | **Account holder** / **Employee with Account** | Пользователь системы = Employee + Account + Access |
| «Применить приказ» *(PATCH)* | **Mark Effective** → **Personnel Event** → **projection** | LR-4, INV-12 |
| «Отменить подписанный приказ» | **Compensating Order** | Void после Signed запрещён |
| «Обновить приказ» *(signed)* | **Compensating Order** + new Documents | INV-8 |
| «Новый сотрудник при rehire» | **Rehire** (same **Employee**) | INV-2 |
| «Восстановить период работы» | **New Employment** on Rehire | INV-4 |
| «Должность сотрудника» *(на Person)* | **Position** on **Employment** / projection | ADR-050 §3.1 vs §3.3 |
| «Роль сотрудника» *(=dolжность)* | **Position** vs **Role** (role code) | ADR-049 §2.1 |
| «Файл приказа» *(=Order)* | **Order** + **Document** | Order — entity; PDF — Document |
| «Событие приказа» | **Personnel Event** *(after Effective)* vs **Order transition** | Order workflow ≠ Event |
| «Черновик сотрудника» *(=draft Employee)* | **Employee draft** (pre-HIRE) vs **Order Draft** | Разные сущности |
| «Заблокировать в архиве» | **Archive** (HR) vs **block Account** (admin) | Разные контуры |
| «PATCH перевода» | **TRANSFER Event** + **Order** | INV-12 |
| «Табельный номер человека» | **employee_code** on **Employee** | Not Person field |

---

## 6. Abbreviations — словарь сокращений

| Сокращение | Расшифровка | Контекст |
|------------|-------------|----------|
| **HR** | Human Resources / кадровый контур | Архитектурное имя контура (ADR-049); не synonym для «HR OS module» |
| **ADR** | Architecture Decision Record | Принятое архитектурное решение |
| **Aggregate** | DDD aggregate | Граница consistency; Employee — personnel aggregate root |
| **Projection** | Read-model / derived state | P-13 ADR-050 |
| **Lifecycle** | Жизненный цикл | Parallel state axes (§ Lifecycle) |
| **Event** | Personnel Event | Сокращение только в HR domain context |
| **UI** | User Interface | Вне scope ADR для layout |
| **API** | Application Programming Interface | Вне scope ADR для endpoints |
| **RBAC** | Role-Based Access Control | док. №15; role codes ADR-049 |
| **e-sign** | Electronic signature | ESignAdapter (future) |
| **ESign** | Electronic Signature adapter | ADR-051 §9 |
| **PDF** | Portable Document Format | `generated_pdf`, `signed_pdf` |
| **OCR** | Optical Character Recognition | Out of scope ADR |
| **FTE** | Full-Time Equivalent | Ставка на Employment |
| **INV** | Architectural Invariant | ADR-050 §6 |
| **LR** | Lifecycle Rule (Order) | ADR-051 §4.5 |
| **OW** | Order Workflow invariant | ADR-051 §10 |
| **ML** | Multilingual rule | ADR-051 §8.4 |
| **PROJ-*** | Implementation project | Roadmap, не ADR |
| **RU / KK** | Russian / Kazakh locale | Bilingual orders |
| **MVP** | Minimum Viable Product | Phase 1 manual sign, single_locale |
| **PII** | Personally Identifiable Information | ADR-058 (planned) |
| **Tenant** | Client isolation | Multitenancy |
| **org-tech** | Organizational-technical contour | ADR-049 `admin` contour |
| **UUID** | Universally Unique Identifier | Entity ids (implementation) |

---

## 7. Cross References — термины по ADR

### ADR-049 — Administrative Architecture

| Термины |
|---------|
| Person, Employee, Account, Access, Role, Client, Organization Unit, Position (catalog), HR contour, org-tech contour, Identity (chain), Aggregate (Account boundary) |

[ADR-049](../adr/ADR-049-administrative-roles-and-responsibility-model.md)

### ADR-050 — Personnel Lifecycle

| Термины |
|---------|
| Person, Employee, Employment, Current Employment, Employment History, Personal File, Personnel Event, Order (entity), Document, Archive, Rehire, Candidate, Identity, Aggregate Root, Content Hub, Projection, Timeline, Lifecycle, Append-only, Immutable, Read-only Archive |

[ADR-050](../adr/ADR-050-personnel-lifecycle-architecture.md)

### ADR-051 — Order Workflow

| Термины |
|---------|
| Order, Order Lifecycle, Draft, Review, Approved, Signed, Effective, Void, Compensating Order, Document Version, Canonical Document, required_locales, Manual Signature, Electronic Signature, Projection (Effective chain), Timeline (via Event) |

[ADR-051](../adr/ADR-051-personnel-order-workflow-architecture.md)

### Связанные документы (не ADR)

| Документ | Назначение |
|----------|------------|
| [ARCHITECTURE_GOVERNANCE](../ARCHITECTURE_GOVERNANCE.md) | Иерархия ADR → Glossary / Roadmap → Implementation |
| [HR Contour Implementation Roadmap](../roadmap/hr-contour-implementation-roadmap.md) | Phase A–E, PROJ-* |
| [Reference catalogs](../reference_catalogs_global_and_client.md) | Client / global справочники |

---

## 8. История изменений

| Дата | Изменение |
|------|-----------|
| 2026-06-30 | Первая версия на основе ADR-049/050/051 Accepted |
