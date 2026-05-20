# Psychological Testing — Architecture Documentation

Версия: Draft 0.1  
Статус: Architecture-only (без production backend/UI/миграций)  
Модуль: `psychological_testing/` (HR OS Level 3 — operational domain)

---

## Назначение

Документация описывает архитектуру **Universal Psychological Testing Platform** — HR-модуля психологического тестирования в рамках [HR Operating System](../architecture/HR_Operating_System_Architecture_Agreement.md).

Модуль проектируется как:

- отдельный operational domain (не global catalog);
- универсальная платформа тестов (не hardcoded MBTI);
- изолированный от Skill Assessment (`skill_assessment/`).

---

## Индекс документов

| # | Документ | Содержание |
|---|----------|------------|
| 00 | **[Next Steps](00_NEXT_STEPS.md)** | **Как двигаться по roadmap (начните здесь)** |
| 01 | [AS-IS Analysis](01_AS_IS_ANALYSIS.md) | Текущее состояние: HR OS placeholder + legacy `07 PsychTest` |
| 02 | [Target Architecture](02_TARGET_ARCHITECTURE.md) | Целевая архитектура, слои, границы с Skill Assessment |
| 03 | [Modular Structure](03_MODULAR_STRUCTURE.md) | Структура пакета, plugin model, research zone |
| 04 | [Universal Test Engine](04_UNIVERSAL_TEST_ENGINE.md) | TestDefinition, registry, state machine, scoring types |
| 05 | [Shared Scoring Architecture](05_SHARED_SCORING_ARCHITECTURE.md) | Scoring pipeline, normalization, mapping 4+1 тестов |
| 06 | [Telegram Integration](06_TELEGRAM_INTEGRATION.md) | Text-out / voice-in / buttons UX, STT, answer_resolver |
| 07 | [AI Integration Boundaries](07_AI_INTEGRATION_BOUNDARIES.md) | Разрешённое и запрещённое использование AI |
| 08 | [RBAC, Storage, Versioning](08_RBAC_STORAGE_VERSIONING.md) | Доступ, хранение, версионирование |
| 09 | [Shared vs Test-Specific](09_SHARED_VS_TEST_SPECIFIC.md) | Классификация компонентов |
| 10 | [Implementation Roadmap](10_IMPLEMENTATION_ROADMAP.md) | Поэтапный план внедрения |
| 11 | [Technical Debt](11_TECHNICAL_DEBT.md) | Технический долг legacy и migration |
| 12 | [Risks](12_RISKS.md) | Реестр рисков и митигации |
| 13 | [MBTI Extension Point](13_MBTI_EXTENSION_POINT.md) | MBTI: 3 Colab-подхода, scoring, research vs production |

---

## Глоссарий

| Термин | Определение |
|--------|-------------|
| **shared_engine** | Универсальное ядро платформы тестов (scoring pipeline, STT, resolver) |
| **test plugin** | Test-specific логика в `tests/{test_id}/` (PAEI, DISC, MBTI и т.д.) |
| **TestDefinition** | YAML/JSON-дескриптор теста: item bank, scoring_type, версия |
| **scoring_type** | Стратегия подсчёта (`likert_sum`, `dichotomy_weighted_choice`, …) |
| **answer_resolver** | Детерминированный mapping transcript → structured answer |
| **research/** | Зона экспериментов; не production без promotion checklist |
| **pt_*** | Префикс таблиц модуля (future, mirror `sa_*`) |

---

## Зафиксированные решения

1. HR-модуль живёт в `psychological_testing/`, **не** в global directories.
2. Psychological Testing **≠** Skill Assessment — отдельный package, API prefix, DB prefix.
3. Telegram UX: **текстовый вопрос** + **inline-кнопки** + явная подсказка «можно ответить голосом»; inbound: голос (primary), кнопка или текст (fallback).
4. Scoring — **детерминированный**; LLM не используется для mapping ответа в score.
5. MBTI — test plugin; вывод **16 типов**; логика из Colab → **Python scripts** → `shared_engine/`.

---

## Colab → Python

| Этап | Что |
|------|-----|
| Reference | Colab в `research/mbti/colab/` |
| Implementation | Python в `research/mbti/scripts/`, `research/scripts/` |
| Validation | Python output == Colab на фиксированных кейсах |
| Production | Promote → `shared_engine/` (Phase 1) |

---

## Структура репозитория

```text
docs/hr-os/psychological_testing/   ← архитектурные документы (этот каталог)
psychological_testing/               ← модуль: research, data, будущий код
  ├── README.md
  ├── research/
  └── data/interpretations/v1/mbti_16_types.yaml
```

---

## Связанные документы

- [HR Operating System Architecture Agreement](../architecture/HR_Operating_System_Architecture_Agreement.md)
- [Архитектурная концепция платформы](../../architecture/архитектурная_концепция_платформы_типовая_инфраструктура_b_2_b.md) §5.8.1
- [Концептуальная модель данных](../../architecture/концептуальная_модель_данных_и_erd_типовая_инфраструктура_b_2_b.md) §8.1
- Reference plugin: [`skill_assessment/`](../../../skill_assessment/)

---

## Scope текущей задачи

**Создано:** architecture markdown + skeleton `psychological_testing/` (research, data).

**Не создано (explicitly out of scope):**

- production backend / API;
- DB migrations;
- UI / workspace activation;
- `shared_engine/` Python code.
