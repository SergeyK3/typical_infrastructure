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
| DISC / HEXACO | `test_full_disc_*`, `test_full_hexaco_*` | — | ✅ auto |
| Голос (STT mock) | `test_voice_in_mock_stt_*` | hint + повтор вопроса | ✅ ожидаемо (dev) |
| Отмена `/cancel` | `test_cancel_clears_session` | — | ✅ |
| `/start` без аргумента → меню | `test_start_without_arg_shows_welcome_not_session` | — | ✅ |
| Повторный `/start` при активной сессии | `test_start_while_active_session_blocked` | — | ✅ |

Команда: `pytest tests/test_psychological_testing_phase3.py tests/test_psychological_testing_mbti_dialog*.py -v`

Live PAEI и Soft Skills подтверждены логами worker (`incoming … /start paei`, `/start soft_skills`, серии `answerCallbackQuery`).

---

## Зафиксированные баги / долг

| ID | Severity | Описание | Статус |
|----|----------|----------|--------|
| PT-E2E-01 | **High** | Несколько `telegram_worker` → Telegram **409 Conflict**; callback в процесс без сессии | **Fixed:** pid-lock + probe 409 |
| PT-E2E-02 | Medium | `/start` без аргумента сразу стартовал MBTI | **Fixed:** меню (`_welcome_text`) |
| PT-E2E-03 | Medium | Новый `/start <test>` без `/cancel` молча заменял сессию | **Fixed:** guard в `start_test` |
| PT-E2E-04 | Low | `STT_PROVIDER=mock`: длинный hint на каждое голосовое | By design (dev) |
| PT-E2E-05 | Low | In-memory: рестарт worker → «Устаревшая кнопка» | Phase 4 (persistence) |
| PT-E2E-06 | Info | DISC/HEXACO в Telegram | **Done:** `/start disc`, `/start hexaco` |
| PT-UX-AKMA | Low | В чате Акмы: «Оценка: E \| Счёт EI: …» | **Fixed:** только в протоколе/отчёте |

---

## Рекомендации перед Phase 4

1. ~~Guard при повторном `/start`~~ — сделано (PT-E2E-03).
2. ~~`/start` без аргумента → welcome~~ — сделано (PT-E2E-02).
3. Smoke-check перед dev: `scripts/skill_assessment/telegram_bot_smoke_check.py` (conflict getUpdates).
4. `integration/hr_core.py` — lookup `Employee` по `telegram_id` (мастер-данные в HR UI).
5. PDF-отчёт в Telegram (порт legacy `enhanced_pdf`).

---

## Exit criteria Phase 3 E2E

- [x] MBTI 16 → type_code + lookup 16 типов
- [x] PAEI → отчёт с %
- [x] Soft Skills → 10 dimension scores
- [x] Кнопки + текст (+ mock voice hint)
- [x] Один worker без 409
- [x] Live PAEI + soft_skills (логи Telegram, chat 7826888928)
- [x] UX: welcome на `/start`, guard при активной сессии
