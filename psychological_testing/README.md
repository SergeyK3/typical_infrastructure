# Psychological Testing — HR Module

Operational HR-модуль психологического тестирования (HR OS Level 3).

**Архитектурная документация:** [docs/hr-os/psychological_testing/](../docs/hr-os/psychological_testing/README.md)

**С чего начать:** [00_NEXT_STEPS.md](../docs/hr-os/psychological_testing/00_NEXT_STEPS.md)

---

## Структура (целевая)

```text
psychological_testing/
├── README.md                 ← вы здесь
├── research/                 ← Colab, эксперименты (Phase 0)
├── data/                     ← item banks, interpretations (versioned)
├── shared_engine/            ← universal test engine (Phase 1)
├── tests/                    ← test plugins: paei, disc, hexaco, soft_skills, mbti
├── integration/              ← hr_core, telegram (Phase 3)
└── infrastructure/           ← pt_* DB models (Phase 4)
```

**Phase 3 (Telegram):** `integration/telegram_adapter.py`, `telegram_worker.py` — см. [00_NEXT_STEPS.md](../docs/hr-os/psychological_testing/00_NEXT_STEPS.md).

**Phase 3b (JSON + HR):** `integration/hr_core.py`, `integration/session_persistence.py` — [15_PHASE3B_PERSISTENCE_AND_HR.md](../docs/hr-os/psychological_testing/15_PHASE3B_PERSISTENCE_AND_HR.md). Включить `PSYCH_TESTING_PERSIST_JSON=1` в `.env`.

**PDF export:** Phases A–E ✅ — [16](../docs/hr-os/psychological_testing/16_PDF_EXPORT_CONTRACT_AND_PLAN.md).

- CLI: `python -m psychological_testing.export_pdf --manifest … --output report.pdf`
- API: `POST /api/psychological-testing/employees/{id}/export-pdf`
- Workspace: кнопка **PDF** в таблице сессий (чекбоксы секций, preview)

Env: `PSYCH_TESTING_PDF_AI=1`, `PSYCH_TESTING_PDF_CACHE=hash|off`, `PSYCH_TESTING_RBAC_EXPORT=0|1`.

**Google Drive (optional):** `PSYCH_TESTING_GDRIVE=1` + service account — [17_GDRIVE_STORAGE.md](../docs/hr-os/psychological_testing/17_GDRIVE_STORAGE.md).

Переменные окружения — **корень репозитория** `10 Typical_infrastructure/.env` (как у `app.settings` и skill_assessment). Шаблон: `.env.example` в том же корне.

Перенос токена из legacy: `07 PsychTest/.env` → `BOT_TOKEN` скопировать как `TELEGRAM_BOT_TOKEN` в корневой `.env`.

```bash
python -m psychological_testing.telegram_worker
```

**Phase 0:** Colab → Python scripts в `research/` (reference only).

```text
research/
├── mbti/colab/          ← notebooks (reference)
├── mbti/scripts/        ← dichotomy_scorer.py, question_selector.py
└── scripts/             ← likert_scorer.py, load_item_bank.py
```

---

## Тесты платформы

| test_id | Статус | scoring_type |
|---------|--------|--------------|
| paei | legacy → migrate | forced_choice_count |
| disc | legacy → migrate | likert_sum |
| hexaco | legacy → migrate | likert_sum |
| soft_skills | legacy → migrate | likert_per_dimension |
| mbti | Colab → plugin | dichotomy_weighted_choice → **16 типов** |

Legacy source: `07 PsychTest` (sibling project).
