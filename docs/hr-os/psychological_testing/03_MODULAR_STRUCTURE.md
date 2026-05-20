# 03 — Modular Structure

Версия: Draft 0.1

---

## 1. Package layout

HR-модуль по образцу `skill_assessment/`, **не** в global directories:

```text
psychological_testing/
├── bootstrap.py              # sys.path + plugin env (mirror skill_assessment)
├── env.py                    # PSYCH_TESTING_* env loader
├── runner.py                 # ASGI entry (future)
├── router.py                 # /api/psychological-testing/* (future)
│
├── domain/
│   ├── entities.py           # TestSession, TestDefinition, ScoreResult
│   ├── test_registry.py      # plugin discovery, TestDefinition loading
│   └── scoring_contracts.py  # ScoringStrategy protocol / ABC
│
├── shared_engine/            # ★ universal platform core
│   ├── item_bank_loader.py
│   ├── question_selector.py
│   ├── response_collector.py
│   ├── voice_pipeline.py
│   ├── answer_resolver.py
│   ├── dichotomy_scorer.py
│   ├── scoring_pipeline.py
│   ├── normalization.py
│   ├── interpretation_engine.py
│   ├── session_state_machine.py
│   └── report_builder.py
│
├── tests/                    # test-specific plugins (NOT global)
│   ├── _template/            # scaffold for new tests
│   ├── paei/
│   ├── disc/
│   ├── hexaco/
│   ├── soft_skills/
│   └── mbti/
│
├── research/                 # ★ research-only zone
│   ├── README.md             # boundary marker + promotion checklist
│   ├── colab/
│   ├── scripts/
│   └── mbti/
│       ├── colab/
│       ├── ai_generated/
│       └── process_orchestrator/
│
├── data/                     # versioned production assets
│   ├── banks/v1/
│   ├── interpretations/v1/
│   └── prompts/v1/
│
├── infrastructure/           # (Phase 4) pt_* ORM models
├── integration/
│   ├── hr_core.py            # app.hr bridge
│   └── telegram_adapter.py
├── adapters/
│   └── telegram_outbound.py
└── schemas/
```

Architecture docs: `docs/hr-os/psychological_testing/` (отдельно от package code).

---

## 2. Test plugin structure

Каждый тест — каталог `tests/{test_id}/`:

```text
tests/mbti/
├── definition.yaml           # TestDefinition
├── answer_patterns.yaml      # resolver rules for voice/text
├── scorer.py                 # optional custom logic
├── interpretation.yaml       # type bands, static text
└── README.md                 # test-specific notes
```

### `_template/` — scaffold для новых тестов

```text
tests/_template/
├── definition.yaml.example
├── answer_patterns.yaml.example
├── scorer.py.example
└── README.md
```

Используется при добавлении MBTI, будущих тестов без изменения core.

---

## 3. Plugin discovery

`domain/test_registry.py`:

1. Scan `tests/*/definition.yaml`
2. Validate schema (test_id, version, scoring_type)
3. Register in memory map: `test_id → TestDefinition + optional Scorer`
4. Reject plugins in `research/` (not in registry)

```yaml
# tests/disc/definition.yaml (example)
test_id: disc
version: "1.0.0"
scoring_type: likert_sum
item_bank: data/banks/v1/disc_items.csv
scales: [D, I, S, C]
response_scale: { min: 1, max: 5 }
normalization: { method: average_per_scale }
interpretation: data/interpretations/v1/disc.csv
ai_prompt: data/prompts/v1/disc_system_res.txt
```

---

## 4. Research zone rules

`research/` — **explicitly NOT production**.

| Rule | Detail |
|------|--------|
| Location | `psychological_testing/research/` only |
| Colab | Reference only — логика **извлекается** в Python scripts |
| Scripts | **Primary implementation** в Phase 0 (`research/scripts/`, `research/mbti/scripts/`) |
| Import | Production code **must not** import from `research/` |
| Promotion | Python script validated → move to `shared_engine/` or `tests/*` → version in `data/` |

### Colab → Python (Phase 0 workflow)

```text
research/mbti/colab/*.ipynb     ← сохранить как reference
        ↓ извлечь логику
research/mbti/scripts/*.py      ← реализовать на Python
        ↓ validate (same I/O as Colab)
shared_engine/ (Phase 1)        ← promote после проверки
```

| Source | Target Python script |
|--------|---------------------|
| Notebook 1 (structured MBTI) | `research/mbti/scripts/dichotomy_scorer.py` |
| Notebook 2 (AI questions) | `research/mbti/scripts/ai_generated_mbti.py` |
| Notebook 3 (orchestrator) | `research/mbti/scripts/process_orchestrator.py` |
| 07 PsychTest `scoring.py` | `research/scripts/likert_scorer.py` |
| Item banks CSV | `research/scripts/load_item_bank.py` |

### Promotion checklist (research → production)

- [ ] Scoring reproducible (same input → same output)
- [ ] Item bank versioned in `data/banks/v1/`
- [ ] No direct OpenAI/VseGPT in production path (gateway only)
- [ ] Answer resolver patterns documented in `answer_patterns.yaml`
- [ ] Unit tests for scorer (future)
- [ ] Review: not violating HR OS §11

---

## 5. Data directory versioning

```text
data/
├── banks/
│   └── v1/
│       ├── paei_items.csv
│       ├── disc_items.csv
│       ├── hexaco_items.csv
│       ├── soft_skills_items.csv
│       └── mbti_items.yaml
├── interpretations/v1/
└── prompts/v1/
```

Breaking changes → `v2/` directory; sessions pin version at start.

---

## 6. Integration with platform core

Mirror `skill_assessment/integration/hr_core.py`:

```python
# Expected contract (future)
from app.hr import get_employee  # client_id, employee_id → snapshot
```

Fallback stubs when core unavailable (dev mode).

Employee Telegram binding: `Employee.telegram_id` in `app/models.py`.

---

## 7. Config isolation

| Module | Env prefix | Example |
|--------|------------|---------|
| Skill Assessment | `SKILL_ASSESSMENT_*` | `SKILL_ASSESSMENT_STT_PROVIDER` |
| Psych Testing | `PSYCH_TESTING_*` | `PSYCH_TESTING_STT_PROVIDER` |

Не смешивать конфиги модулей.

---

## 8. Documentation map

| Code location | Docs location |
|---------------|---------------|
| `psychological_testing/` | `docs/hr-os/psychological_testing/` |
| `tests/mbti/` | `13_MBTI_EXTENSION_POINT.md` |
| `research/` | `research/README.md` + roadmap Phase 0 |

---

## 9. What NOT to put in global directories

Запрещено выносить в:

- `app/routers/` global catalogs;
- `static/global/`;
- `app/models.py` psych-specific entities (use `pt_*` in plugin);
- `skill_assessment/` shared code.

Shared platform touchpoints только через: `app.hr`, RBAC, storage, notification bus (future).
