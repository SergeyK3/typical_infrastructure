# HR Operating System — Архитектурное соглашение  
## Проект «Типовая инфраструктура»

Версия: Draft 0.1  
Статус: Базовое архитектурное соглашение  
Назначение: фиксация архитектурного подхода к HR-модулям

---

# 1. Общая концепция

Проект «Типовая инфраструктура» развивается не как набор справочников или отдельных HR-утилит, а как:

```text
HR Operating System (HR OS)
```

То есть как единая корпоративная платформа:
- управления HR-процессами,
- оценки персонала,
- развития сотрудников,
- контроля регламентов,
- корпоративной аналитики,
- AI-поддержки HR-функций.

---

# 2. Базовая архитектурная модель

Система строится как трехуровневая архитектура.

---

# 3. Уровни системы

## 3.1. Уровень 1 — Platform Core / Global Layer

Назначение:
- platform metadata,
- глобальные классификаторы,
- platform governance,
- RBAC,
- shared infrastructure.

### Содержит:
- организации,
- глобальные роли,
- permissions,
- типы сущностей,
- платформенные настройки,
- базовые классификаторы,
- системные metadata.

### Не содержит:
- operational HR-процессы,
- workflow,
- тестирования,
- обучение,
- аттестации,
- сертификаты,
- документы сотрудников.

---

## 3.2. Уровень 2 — Organization Layer

Назначение:
- tenant/business scope.

### Содержит:
- локальные подразделения,
- локальные должности,
- локальные KPI,
- локальные навыки,
- сотрудников,
- аккаунты,
- локальные политики организации,
- локальные HR-настройки.

---

## 3.3. Уровень 3 — HR Modules Layer

Назначение:
- operational HR domain.

HR-модули рассматриваются как:
- отдельный домен,
- отдельная business-process layer,
- operational subsystem.

---

# 4. Зафиксированное архитектурное решение

## HR-модули НЕ выносятся в глобальные справочники.

Следующие разделы являются самостоятельными HR-доменами:

```text
HR-МОДУЛИ
 ├── Психологические тестирования
 ├── Обучение
 ├── Аттестации
 ├── Оценка навыков (Skill Assessment)
 ├── Административные назначения
 ├── Дисциплинарные поощрения и взыскания
 ├── Сертификаты
 ├── AI-ассистенты
 ├── Документооборот
 ├── Комплаенс
 ├── Медосмотры
 └── Аккредитации
```

---

# 5. Причины принятого решения

## 5.1. Разделение metadata и operational domain

Глобальный уровень:
- metadata,
- platform configuration,
- shared classifiers.

HR-модули:
- процессы,
- workflow,
- события,
- lifecycle,
- аналитика,
- уведомления,
- AI.

---

## 5.2. Multi-tenant архитектура

Организации могут:
- включать/отключать модули,
- использовать разные политики,
- иметь разные процессы,
- иметь разные наборы тестов,
- использовать разные версии workflow.

---

## 5.3. RBAC и безопасность

Operational HR-данные:
- требуют сложного разграничения доступа,
- organization-scoped,
- department-scoped,
- role-scoped.

---

## 5.4. Масштабируемость

Подход HR OS позволяет:
- независимо развивать модули,
- внедрять AI,
- добавлять workflow,
- строить event-driven архитектуру,
- избегать монолитного «HR-супер-справочника».

---

# 6. Принципы построения HR-модулей

Все HR-модули строятся по единым принципам.

---

## 6.1. Unified Engine Approach

Не допускается:
- отдельная кодовая база под каждый HR-процесс,
- отдельный UI под каждый тип оценки,
- дублирование workflow engine.

---

## 6.2. Reusable Components

Модули должны переиспользовать:
- RBAC,
- notifications,
- audit log,
- workflow,
- attachments,
- AI services,
- reporting,
- analytics.

---

## 6.3. Shared Infrastructure

Общими являются:
- users,
- organizations,
- departments,
- permissions,
- AI gateway,
- storage,
- notification bus,
- event system.

---

# 7. Архитектурный статус модуля «Психологические тестирования»

Модуль:

```text
Психологические тестирования
```

является:
- operational HR-module,
- частью HR OS,
- а не глобальным справочником.

**Архитектурная документация модуля:**  
[`docs/hr-os/psychological_testing/README.md`](../psychological_testing/README.md)  
**Практический старт:** [`00_NEXT_STEPS.md`](../psychological_testing/00_NEXT_STEPS.md)

---

# 8. Допустимые внутренние system entities

Допускается наличие скрытых internal entities:

```text
test_templates
workflow_templates
scoring_schemas
AI prompt templates
interpretation schemas
```

Но:
- без отдельного глобального UI,
- без выноса в sidebar глобального уровня,
- как internal platform metadata.

---

# 9. Принципы развития HR OS

## Этап 1
Infrastructure first:
- RBAC,
- organizations,
- users,
- audit,
- notifications,
- workflow foundation.

---

## Этап 2
Operational modules:
- Psychological Testing,
- Learning,
- Assessments.

---

## Этап 3
Analytics:
- dashboards,
- team analytics,
- competency analytics.

---

## Этап 4
AI augmentation:
- AI summaries,
- AI insights,
- recommendations,
- predictive analytics.

---

# 10. Стратегическое позиционирование

Система развивается как:

```text
Enterprise HR Operating System
```

а не:
- LMS,
- ERP-справочник,
- отдельный HR-портал,
- набор тестов.

---

# 11. Архитектурные ограничения

На ранних этапах запрещается:
- строить AI-психолога,
- автоматизировать кадровые решения,
- делать AI hiring reject,
- использовать психометрию как единственный критерий оценки,
- строить монолитный global HR directory.

---

# 12. Ключевое зафиксированное решение

## Зафиксировано:

```text
HR Modules
=
separate operational domain
```

## Не допускается:

```text
global HR super-directory
```

---

# 13. Целевое состояние системы

Целевая архитектура:

```text
Platform Core
    ↓
Organization Layer
    ↓
HR Operating System
    ↓
AI-assisted HR workflows
```

с независимыми:
- HR-модулями,
- workflow,
- аналитикой,
- AI-сервисами,
- governance-механизмами.
