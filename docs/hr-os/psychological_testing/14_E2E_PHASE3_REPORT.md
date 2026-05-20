# 14 — E2E Phase 3 Report (@orgskilldevbot)

Дата: 2026-05-20  
Бот: [@orgskilldevbot](https://t.me/orgskilldevbot)  
Worker: `python -m psychological_testing.telegram_worker` (один процесс, `.venv`)

---

## Прогон

| Сценарий | Авто (adapter mock) | Live Telegram | Результат |
|----------|---------------------|---------------|-----------|
| MBTI 16 вопросов (4/ось), кнопки | `test_full_mbti_16_via_buttons` | 16 callback + отчёт (chat 7826888928, 08:55) | ✅ |
| PAEI 5 вопросов, кнопки | `test_full_paei_via_buttons` | 5 callback + отчёт (09:12–09:14) | ✅ |
| PAEI, текст (п/a/e/i/п) | `test_paei_text_answer_completes` | — | ✅ auto |
| Soft Skills 10 вопросов, кнопки 1–5 | `test_full_soft_skills_via_buttons` | 10 callback ×2 (09:14, 09:47) | ✅ |
| MBTI dialog (Акма), голос | `test_psychological_testing_mbti_dialog*` | ручной прогон | ✅ |
| HEXACO 6 вопросов, кнопки 1–5 (blind UX) | `test_full_hexaco_via_buttons` | 6 callback + отчёт (13:52–13:53) | ✅ |
| DISC 4 вопроса, кнопки 1–5 | `test_full_disc_via_buttons` | 4 callback + отчёт (13:54–13:55) | ✅ |
| JSON persistence (`PERSIST_JSON=1`) | unit / adapter | 2 файла в `data/sessions/v1/2026-05-20/` | ✅ |
| Голос (STT mock) | `test_voice_in_mock_stt_*` | hint + повтор вопроса | ✅ ожидаемо (dev) |
| Отмена `/cancel` | `test_cancel_clears_session` | — | ✅ |
| `/start` без аргумента → меню | `test_start_without_arg_shows_welcome_not_session` | — | ✅ |
| Повторный `/start` при активной сессии | `test_start_while_active_session_blocked` | — | ✅ |

Команда: `pytest tests/test_psychological_testing_phase3.py tests/test_psychological_testing_mbti_dialog*.py -v`

Live PAEI, Soft Skills, HEXACO и DISC подтверждены логами worker (chat **7826888928**):

- `/start hexaco` → 6× `answerCallbackQuery` → `session result saved …56cffcd3…json`
- `/start disc` → 4× `answerCallbackQuery` → `session result saved …095de8a4…json`

HEXACO: blind intro (без названий факторов) + вопросы только `[N/6] HEXACO`.

---

## Зафиксированные баги / долг

| ID | Severity | Описание | Статус |
|----|----------|----------|--------|
| PT-E2E-01 | **High** | Несколько `telegram_worker` → Telegram **409 Conflict**; callback в процесс без сессии | **Fixed:** pid-lock + probe 409 |
| PT-E2E-02 | Medium | `/start` без аргумента сразу стартовал MBTI | **Fixed:** меню (`_welcome_text`) |
| PT-E2E-03 | Medium | Новый `/start <test>` без `/cancel` молча заменял сессию | **Fixed:** guard в `start_test` |
| PT-E2E-04 | Low | `STT_PROVIDER=mock`: длинный hint на каждое голосовое | By design (dev) |
| PT-E2E-05 | Low | In-memory: рестарт worker → «Устаревшая кнопка» | **Partial:** JSON при `DONE` ✅; resume активной сессии → Phase 4 |
| PT-E2E-06 | Info | DISC/HEXACO в Telegram | **Done:** live E2E 2026-05-20 13:52–13:55 |
| PT-E2E-07 | Info | `hr_core`: несколько `Employee` на один `telegram_id` → warning «using newest» | By design (dev DB); нормализовать мастер-данные |
| PT-UX-AKMA | Low | В чате Акмы: «Оценка: E \| Счёт EI: …» | **Fixed:** только в протоколе/отчёте |
| PT-BANK-01 | Info | DISC mini bank: 4 vs 8 в legacy; HEXACO: 6 vs 12 | Backlog (LEGACY_RECONCILIATION.md) |

---

## Рекомендации перед Phase 4

1. ~~Guard при повторном `/start`~~ — сделано (PT-E2E-03).
2. ~~`/start` без аргумента → welcome~~ — сделано (PT-E2E-02).
3. Smoke-check перед dev: `scripts/skill_assessment/telegram_bot_smoke_check.py` (conflict getUpdates).
4. ~~`PSYCH_TESTING_PERSIST_JSON=1` + запись JSON~~ — live ✅ (hexaco + disc).
5. `integration/hr_core.py` — уникальный `Employee` на `telegram_id` (сейчас warning при дублях).
6. PDF-отчёт по запросу HR из JSON (не legacy monolith) — [16_PDF_EXPORT_CONTRACT_AND_PLAN.md](16_PDF_EXPORT_CONTRACT_AND_PLAN.md).

---

## Exit criteria Phase 3 E2E

- [x] MBTI 16 → type_code + lookup 16 типов
- [x] PAEI → отчёт с %
- [x] Soft Skills → 10 dimension scores
- [x] Кнопки + текст (+ mock voice hint)
- [x] Один worker без 409
- [x] Live PAEI + soft_skills (логи Telegram, chat 7826888928)
- [x] Live HEXACO (6 вопросов, blind UX) + DISC (4 вопроса)
- [x] JSON persistence при завершении (`PSYCH_TESTING_PERSIST_JSON=1`)
- [x] UX: welcome на `/start`, guard при активной сессии
