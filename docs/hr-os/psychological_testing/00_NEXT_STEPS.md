# 00 — Next Steps: как двигаться по roadmap

Версия: Draft 0.1

Практическое руководство: **что делать сейчас**, опираясь на [10_IMPLEMENTATION_ROADMAP.md](10_IMPLEMENTATION_ROADMAP.md).

---

## Где что лежит

| Что | Путь |
|-----|------|
| Архитектурные документы (14 файлов) | `docs/hr-os/psychological_testing/` |
| Точка входа модуля | `psychological_testing/README.md` |
| Research zone | `psychological_testing/research/` |
| MBTI 16 типов (reference) | `psychological_testing/data/interpretations/v1/mbti_16_types.yaml` |
| Legacy код (4 теста) | `../07 PsychTest/` (sibling) |
| Reference plugin | `skill_assessment/` |
| Секреты / env (не в `docs/`) | корень репо: `10 Typical_infrastructure/.env` (шаблон `.env.example`) |
| Legacy bot token | `07 PsychTest/.env` → `BOT_TOKEN` перенести как `TELEGRAM_BOT_TOKEN` |

---

## Phase 4a (срез, 2026-05-20) — назначения HR

Согласовано с [10_IMPLEMENTATION_ROADMAP.md](10_IMPLEMENTATION_ROADMAP.md) §6 (Org test assignment workflow), без полного RBAC/PDF.

```text
☑ pt_test_assignments (SQLite) + API /api/psychological-testing/assignments
☑ Программа standard_hr_v1: mbti → soft_skills → paei|hexaco|disc
☑ Telegram: проверка очереди при /start; уведомление POST …/notify
☑ Workspace: назначить / уведомить; toast вместо alert; дедлайн 3 раб. дня + правка в таблице
☐ UNC + сервисный аккаунт на prod (инфра)
☐ RBAC, pt_test_sessions в БД, напоминания по cron
```

---

## Вы сейчас здесь: Phase 3 (Telegram)

Phase 0–2 ✅ (engine + plugins + session без Telegram). Следующий шаг — **живой бот** (токен в **корневом** `.env`) и ручная проверка на планшете.

### Phase 3 — сделано в коде

```text
☑ adapters/telegram_outbound.py (mock | http)
☑ adapters/telegram_keyboards.py (pt:session:item:value)
☑ integration/session_store.py (in-memory)
☑ integration/telegram_adapter.py (кнопка / текст / голос)
☑ integration/telegram_poller.py (long polling)
☑ telegram_worker.py — отдельный процесс
☑ services/stt_service.py (mock | openai Whisper)
☑ voice_pipeline → OpenAI при PSYCH_TESTING_STT_PROVIDER=openai
☑ pytest tests/test_psychological_testing_phase3.py
```

### Запуск бота (когда добавите токен)

В **`10 Typical_infrastructure/.env`** (тот же файл, что для FastAPI / skill_assessment):

```bash
# из 07 PsychTest/.env: значение BOT_TOKEN → сюда:
TELEGRAM_BOT_TOKEN=...

PSYCH_TESTING_ENABLE_POLLING=1
PSYCH_TESTING_TELEGRAM_OUTBOUND=http
# опционально для короткого MBTI в dev:
PSYCH_TESTING_MBTI_QUESTIONS_PER_AXIS=1
```

Переменные перечислены в корневом `.env.example` (секция Psychological testing).

```bash
python -m psychological_testing.telegram_worker
```

Команды в чате: `/start mbti`, `/start paei`, `/start soft_skills`, `/cancel`.

DISC/HEXACO в Telegram: `/start disc`, `/start hexaco` (likert_sum, mini banks v1).

---

## Phase 0 (Research Foundation) — архив

Архитектура ✅ готова. Следующий шаг — **наполнить research zone**, не писать production backend.

### Неделя 1 — Colab → Python scripts

```text
☑ Сохранить Colab как reference → psychological_testing/research/mbti/colab/
☑ Реализовать research/mbti/scripts/dichotomy_scorer.py
      (логика calculate_type_from_answers + question selection из notebook 1)
☑ Реализовать research/scripts/likert_scorer.py (из 07 PsychTest scoring.py)
☑ Реализовать research/scripts/load_item_bank.py (CSV/YAML loader, draft)
☑ Извлечь 48 вопросов из notebook 1 → data/banks/v1/mbti_items.yaml
      (export: python -m psychological_testing.research.mbti.scripts.export_mbti_items_from_colab)
☑ Заполнить тексты strengths/growth_areas в mbti_16_types.yaml (16 типов, draft)
```

### Неделя 2 — validate Python scripts

```text
☑ Прогнать dichotomy_scorer.py на 5–10 фиксированных сессиях (unit-style, без Colab)
      (pytest tests/test_psychological_testing_research.py — 10 passed)
☑ Проверить: каждый результат — один из 16 type_code
☑ Сверить likert_scorer.py с DISC/HEXACO sample data
      (pytest tests/test_likert_legacy_parity.py)
☑ Задокументировать расхождения CSV vs bot (DISC 4 vs 8 items)
      → psychological_testing/research/LEGACY_RECONCILIATION.md
```

### Неделя 3–4 — voice/button resolver prototype (Python scripts)

```text
☑ research/scripts/answer_resolver_mbti.py — A/B mapping для голоса и текста
☑ Mock STT input: «А» / «вариант первый» → pole (CLI: python -m ...answer_resolver_mbti)
      (pytest tests/test_answer_resolver_mbti.py)
□ Без Colab runtime — только Python
```

**Exit criteria Phase 0:** Python-скрипты воспроизводят Colab-логику; все 5 тестов имеют scoring_type; MBTI выдаёт один из 16 типов.

---

## Phase 1 — когда начинать

Стартуйте Phase 1 (`shared_engine/`), когда:

- MBTI item bank в YAML существует;
- dichotomy_scorer воспроизводит notebook 1;
- 16 типов описаны в `mbti_16_types.yaml`.

Первые файлы Phase 1:

```text
psychological_testing/
├── domain/test_registry.py
├── shared_engine/dichotomy_scorer.py
├── shared_engine/scoring_pipeline.py
└── tests/mbti/definition.yaml
```

Unit-тест: фиксированные ответы → `type_code == "INTJ"` (и другие типы из 16).

---

## Phase 2 — test plugins

Порядок миграции (от простого к сложному):

1. **DISC / HEXACO** — `likert_sum`, уже есть `scoring.py`
2. **PAEI** — `forced_choice_count`
3. **Soft Skills** — `likert_per_dimension`
4. **MBTI** — `dichotomy_weighted_choice` + lookup 16 типов

---

## Phase 3 — Telegram (почти закрыта)

☑ Outbound + keyboards + adapter + poller + worker (см. выше)  
☑ Авто E2E adapter: MBTI 16, PAEI, soft_skills (`tests/test_psychological_testing_phase3.py`)  
☑ Live MBTI 16 на @orgskilldevbot (логи worker)  
☑ Live PAEI + soft_skills на @orgskilldevbot (логи 2026-05-20, chat 7826888928)  
☑ DISC + HEXACO в SessionEngine + Telegram (`/start disc`, `/start hexaco`)  
☑ UX: `/start` без аргумента → меню; повторный `/start` при активной сессии → /cancel  
☑ MBTI dialog: без техстрок «Оценка: … \| Счёт …» в чате  
☑ Отчёт и баги: [14_E2E_PHASE3_REPORT.md](14_E2E_PHASE3_REPORT.md)  
☑ Каркас Phase 3b: [15_PHASE3B_PERSISTENCE_AND_HR.md](15_PHASE3B_PERSISTENCE_AND_HR.md)  
☑ `integration/hr_core.py` — resolve по `telegram_id` (+ dev fallback)  
☑ `integration/session_persistence.py` — JSON v1, файлы при `PSYCH_TESTING_PERSIST_JSON=1`  
☑ Live DISC + HEXACO на @orgskilldevbot (2026-05-20, chat 7826888928)  
☑ `PERSIST_JSON=1` — live: JSON в `data/sessions/v1/2026-05-20/` (hexaco + disc)  
□ PDF — экспорт из JSON (Phase 4 или поздний 3b)  

UX-шаблоны: [06_TELEGRAM_INTEGRATION.md](06_TELEGRAM_INTEGRATION.md)

---

## Phase 4 — production (после 3b)

Только платформенная обвязка — **логика тестов и Telegram уже готовы**:

- `pt_*` ORM + миграции (тот же JSON в `result_json` / нормализованные таблицы)
- FastAPI router, RBAC (`hr.psych_testing.*`)
- Workspace UI: сессии, просмотр, export PDF
- Resume сессии после рестарта worker (`pt_telegram_bindings`)
- Корпоративное хранилище вместо локальных JSON (опционально)

---

## Что НЕ делать сейчас

- ❌ FastAPI router / migrations
- ❌ Workspace UI activation
- ❌ Запуск Colab как runtime (только reference)
- ❌ Копировать `telegram_test_bot.py` as-is
- ❌ LLM для mapping голосовых ответов
- ❌ MBTI notebook 2/3 в production

---

## MBTI: 16 типов в выводе

Scoring → `type_code` (4 буквы) → **обязательный lookup** в `mbti_16_types.yaml`.

Отчёт пользователю **всегда** содержит:

1. **Ваш тип: INTJ — Стратег**
2. Уровни по осям E/I, S/N, T/F, J/P (1–3)
3. Сильные стороны и зоны роста (из YAML или AI summary поверх YAML)
4. Disclaimer: не единственный критерий HR-оценки

Подробнее: [13_MBTI_EXTENSION_POINT.md](13_MBTI_EXTENSION_POINT.md) §3.7

---

## Быстрые ссылки

| Вопрос | Документ |
|--------|----------|
| Как устроен engine? | [04_UNIVERSAL_TEST_ENGINE.md](04_UNIVERSAL_TEST_ENGINE.md) |
| Как считаются баллы? | [05_SHARED_SCORING_ARCHITECTURE.md](05_SHARED_SCORING_ARCHITECTURE.md) |
| Telegram голос + кнопки? | [06_TELEGRAM_INTEGRATION.md](06_TELEGRAM_INTEGRATION.md) |
| MBTI specifics? | [13_MBTI_EXTENSION_POINT.md](13_MBTI_EXTENSION_POINT.md) |
| Tech debt legacy? | [11_TECHNICAL_DEBT.md](11_TECHNICAL_DEBT.md) |

---

## Рекомендуемый порядок чтения

1. [README.md](README.md) — обзор
2. **Этот документ** — action plan
3. [10_IMPLEMENTATION_ROADMAP.md](10_IMPLEMENTATION_ROADMAP.md) — фазы
4. [03_MODULAR_STRUCTURE.md](03_MODULAR_STRUCTURE.md) — куда класть файлы
5. [13_MBTI_EXTENSION_POINT.md](13_MBTI_EXTENSION_POINT.md) — если работаете с MBTI
