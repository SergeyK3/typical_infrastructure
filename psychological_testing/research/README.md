# Research Zone — Psychological Testing

**Статус:** research-only. Код отсюда **не импортируется** в production без promotion checklist.

Архитектура: [docs/hr-os/psychological_testing/03_MODULAR_STRUCTURE.md](../docs/hr-os/psychological_testing/03_MODULAR_STRUCTURE.md) §4

---

## Что класть сюда

| Папка | Содержание |
|-------|------------|
| `colab/` | Исходники логики (reference) — **не runtime** |
| `scripts/` | **Python-реализация** логики из Colab и 07 PsychTest |
| `mbti/colab/` | 3 MBTI notebooks (source only) |
| `mbti/scripts/` | Python: dichotomy_scorer, selection, report (из notebook 1) |
| `mbti/ai_generated/` | Notebook 2 → `mbti/scripts/ai_generated_mbti.py` (research) |
| `mbti/process_orchestrator/` | Notebook 3 → `mbti/scripts/process_orchestrator.py` (research) |
| `sessions/` | JSON dumps тестовых сессий (dev) |

---

## Promotion checklist (research → production)

- [ ] Scoring воспроизводим (same input → same output)
- [ ] Item bank версионирован в `data/banks/v1/`
- [ ] Нет direct OpenAI/VseGPT в production path
- [ ] `answer_patterns.yaml` для voice/button resolver
- [ ] Не нарушает HR OS §11 (no AI-psychologist, no auto HR decisions)

---

## Принцип: Colab → Python

**Colab-ноутбуки — источник логики**, не production runtime.

| Colab (reference) | Python script (реализация) |
|-------------------|----------------------------|
| `research/mbti/colab/structured_questions_scoring.ipynb` | `research/mbti/scripts/dichotomy_scorer.py` |
| `research/mbti/colab/ai_generated_questions.ipynb` | `research/mbti/scripts/ai_generated_mbti.py` (research only) |
| `research/mbti/colab/process_orchestrator_v3.ipynb` | `research/mbti/scripts/process_orchestrator.py` (research only) |
| `07 PsychTest/src/psytest/scoring.py` | `research/scripts/likert_scorer.py` |

Workflow:

```text
Colab / legacy code  →  извлечь логику  →  Python script  →  validate  →  promote в shared_engine/
```

---

## Следующий шаг (Phase 0)

1. ~~Скопировать Colab notebooks → `research/mbti/colab/`~~ ✅
2. ~~Python-скрипты scoring / loader~~ ✅ (`research/scripts/`, `research/mbti/scripts/`)
3. ~~Экспорт 48 вопросов~~ ✅ `python -m psychological_testing.research.mbti.scripts.export_mbti_items_from_colab`
4. ~~Сверка likert с DISC/HEXACO~~ ✅ → `LEGACY_RECONCILIATION.md`, `tests/test_likert_legacy_parity.py`
5. ~~`mbti_16_types.yaml` контент~~ ✅ draft (16 типов)
6. ~~`answer_resolver_mbti.py`~~ ✅ + `tests/test_answer_resolver_mbti.py`

**Phase 0 exit:** `pytest tests/test_psychological_testing_research.py tests/test_likert_legacy_parity.py tests/test_answer_resolver_mbti.py` (21 passed)
