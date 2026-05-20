# Legacy reconciliation — 07 PsychTest vs target module

Версия: 0.1 (Phase 0)

Источник legacy: `../07 PsychTest/` (sibling project).

---

## Likert scoring (`likert_sum`)

| Проверка | Результат |
|----------|-----------|
| `research/scripts/likert_scorer.py` vs `07 PsychTest/src/psytest/scoring.py` | **Совпадает** на банках CSV (pytest `test_likert_legacy_parity.py`) |
| Reverse coding | `max_val + 1 - answer` при `reverse == 1` |
| Агрегация | `sum` по `scale` (не среднее) |

**Важно:** Telegram-бот для DISC после опроса вызывает `convert_disc_to_average()` — **среднее 1–5 по шкале**, а не сумма.  
Target normalization: `tests/disc/definition.yaml` → `normalization: { method: average_per_scale }` для отчётов, совместимых с ботом.

---

## DISC — расхождение банка и бота (D9)

| Источник | Кол-во вопросов | Формат |
|----------|-----------------|--------|
| `data/bank/disc_items.csv` | **4** | 1 item на шкалу D/I/S/C, Likert 1–5, `scoring.py` |
| `data/prompts/disc_user.txt` → `DISC_QUESTIONS` | **8** | 2 вопроса на категорию (D,I,S,C), бот суммирует → **среднее** |
| Fallback в `telegram_test_bot.py` | **1** | forced-choice A/B/C/D (если файл не загрузился) |

**Рекомендация Phase 2:** объединить 8 текстов из `disc_user.txt` в `data/banks/v1/disc_items.yaml` (8 rows) или явно зафиксировать production = 4-item short form.

---

## HEXACO — расхождение банка и бота (D6)

| Источник | Кол-во | Шкалы |
|----------|--------|-------|
| `data/bank/hexaco_items.csv` | **2** | только `H` (Honesty-Humility) |
| `HEXACO_QUESTIONS` в боте | **6** | H, E, X, A, C, O (hardcoded) |

CSV-банк **неполный** для 6-факторной модели. Миграция Phase 2: полный item bank + проверка mapping A/C (риск D6 в tech debt).

---

## PAEI / Soft Skills (кратко)

| Тест | Legacy scoring | Target `scoring_type` |
|------|----------------|----------------------|
| PAEI | forced choice → count | `forced_choice_count` |
| Soft Skills | 1 Likert на навык | `likert_per_dimension` |

Скрипты Phase 0: `likert_scorer.py` (DISC/HEXACO CSV), PAEI/Soft — Phase 2 plugins.

---

## MBTI

| Legacy | Target |
|--------|--------|
| Colab `QUESTIONS` inline | `data/banks/v1/mbti_items.yaml` (48 items) ✅ |
| 3 Colab paradigms | Production: **structured only** (`dichotomy_scorer`) |

---

## Следующие действия

1. Phase 2: расширить `disc_items` / `hexaco_items` в YAML v1
2. Phase 2: `forced_choice_count` для PAEI из `paei_items.csv`
3. Не копировать `telegram_test_bot.py` as-is (D2)
