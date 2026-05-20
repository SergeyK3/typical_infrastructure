# MBTI Colab — reference only

**Путь:** `psychological_testing/research/mbti/colab/`  
Runtime — только Python в `../scripts/`; ноутбуки не вызываются из production.

## Файлы

| Файл | Роль | Статус |
|------|------|--------|
| `structured_questions_scoring.ipynb` | Notebook 1 — 48 вопросов, `QUESTIONS`, `calculate_type_from_answers` | ✅ |
| `process_orchestrator_v3.ipynb` | Notebook 3 — orchestrator | ✅ research |
| `process_orchestrator_v2.2.ipynb` | Orchestrator v2.2 (archive) | ✅ |
| `testing_v2_akma_dialog.ipynb` | Диалог «Акма» + LLM (≠ structured) | ✅ research → `scripts/akma_dialog.py` |

Экспорт банка: `python -m psychological_testing.research.mbti.scripts.export_mbti_items_from_colab`  
→ `psychological_testing/data/banks/v1/mbti_items.yaml`

## Безопасность

Перед коммитом: убрать API keys / Airtable tokens из ячеек (`testing_v2_akma_dialog.ipynb`).

См. [13_MBTI_EXTENSION_POINT.md](../../../../docs/hr-os/psychological_testing/13_MBTI_EXTENSION_POINT.md)
