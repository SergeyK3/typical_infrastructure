# Architecture Decision Records (ADR)

Реестр архитектурных решений платформы «Типовая инфраструктура».

> **Governance:** иерархия ADR → Glossary / Roadmap → Phase A–E → Implementation — [ARCHITECTURE_GOVERNANCE.md](../ARCHITECTURE_GOVERNANCE.md)

## Индекс

| ADR | Название | Статус |
|-----|----------|--------|
| [ADR-049](./ADR-049-administrative-roles-and-responsibility-model.md) | Административные роли и модель ответственности | **Accepted** |
| [ADR-050](./ADR-050-personnel-lifecycle-architecture.md) | Personnel Lifecycle Architecture (кадровый жизненный цикл) | **Accepted** |
| [ADR-051](./ADR-051-personnel-order-workflow-architecture.md) | Personnel Order Workflow Architecture (workflow приказов) | **Accepted** |

Документы ADR-001–048 могут существовать вне этого репозитория или в истории обсуждений; нумерация сквозная по программе.

## Взаимосвязи ADR

| ADR | Зависит от | Включает / порождает | Назначение |
|-----|------------|----------------------|------------|
| **ADR-049** | UX-REF-001, док. №15, HR OS Agreement | **ADR-050** | Административные роли, три контура, матрица ответственности, принципы Person → Employee → Account → Access |
| **ADR-050** | **ADR-049** | **ADR-051**, ADR-052…059, PROJ-* | **Accepted.** Lifecycle; Employee Aggregate Root |
| **ADR-051** | **ADR-049**, **ADR-050** | PROJ-ORDERS, PROJ-ORDER-WORKFLOW, ADR-052 | **Accepted.** Order workflow; Draft → Effective; OW/LR invariants |

## Формат

- Один ADR — одно архитектурное решение или модель.
- ADR описывает **что** и **почему**; реализация — отдельные проекты в backlog.
- Статусы: *Proposed* → *Accepted* → *Superseded* (при замене новым ADR).

## Базовый стек архитектуры (ADR-049 → ADR-050 → ADR-051, Accepted)

```text
Person → Employee → Employment → Personal File → Orders → Documents → Archive
         ↑ Aggregate Root (ADR-050)
         Order workflow (ADR-051): Draft → Review → Approved → Signed → Effective → Archived
         └────────────► Account → Access   (ADR-049, org-tech)
```

## Architecture Reference (не ADR)

Справочные архитектурные документы фиксируют терминологию и соглашения; **не принимают** новых решений.

| Документ | Назначение |
|----------|------------|
| [HR Domain Glossary](../reference/hr-domain-glossary.md) | Единый словарь терминов кадрового контура (обязательный источник для ADR, PROJ-*, API, UI, кода) |

## Implementation documents (не ADR)

Дорожные карты и планы реализации **не входят** в реестр ADR выше; они ссылаются на принятые ADR и раскладывают их на проекты backlog.

| Документ | Назначение |
|----------|------------|
| [HR Contour Implementation Roadmap](../roadmap/hr-contour-implementation-roadmap.md) | Phase A–E, PROJ-*, guardrails для задач реализации кадрового контура |
