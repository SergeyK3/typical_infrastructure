# 15 — Phase 3b: JSON-результаты, hr_core, граница с Phase 4

Версия: Draft 0.1  
Дата: 2026-05-20

Phase 3 (Telegram E2E) закрыта. **Phase 3b** — сохранение канонического JSON и привязка к Employee **без** полного production backend.

**Phase 4** — только то, что требует платформу целиком: ORM `pt_*`, API, RBAC, workspace UI, PDF как экспорт для HR.

---

## Что входит в Phase 3b (сейчас / следующий спринт)

| # | Артефакт | Статус |
|---|----------|--------|
| 1 | Контракт JSON `pt_session_result` v1 | ✅ этот документ + `integration/session_persistence.py` |
| 2 | `integration/hr_core.py` — мост к `Employee` / `app.hr` | ✅ каркас |
| 3 | Сохранение JSON при `DONE` (файлы `data/sessions/v1/`) | ✅ за флагом `PSYCH_TESTING_PERSIST_JSON=1` |
| 4 | Lookup `telegram_id` → `employee_id` при `/start` | ✅ в adapter (с fallback dev) |
| 5 | Текст в Telegram сразу после теста | ✅ уже есть |

## Что остаётся на Phase 4

| # | Задача | Почему не 3b |
|---|--------|----------------|
| 1 | Таблицы `pt_test_sessions`, `pt_session_responses`, `pt_session_scores` | Общий `app.db`, миграции, `create_all` |
| 2 | FastAPI router `/api/hr/psych-testing/...` | RBAC, workspace |
| 3 | Workspace UI: список сессий, просмотр, export | Frontend HR OS |
| 4 | RBAC (`hr.psych_testing.*`) | Платформенные роли |
| 5 | PDF из JSON (шаблон, `sendDocument` опционально) | Рендер, не блокер Telegram |
| 6 | Персистентность активной сессии (рестарт worker) | `pt_telegram_bindings` + resume |
| 7 | Сервисный аккаунт / корпоративное хранилище | Если не локальные JSON-файлы |

**Итог:** после Phase 3b для пользователя в боте всё работает как сейчас + результаты пишутся в JSON. Phase 4 = «подключить к HR OS как продукт».

---

## Канонический документ: `pt_session_result` v1

Один файл / одна строка БД на завершённую сессию. PDF **не** источник истины — только экспорт из этого JSON.

```json
{
  "schema_version": "1.0.0",
  "session_id": "uuid",
  "client_id": "org-1",
  "employee_id": "emp-42",
  "employee_display_name": "Иванов Иван",
  "telegram_chat_id": "7826888928",
  "test_id": "mbti",
  "test_version": "1.0.0",
  "delivery_mode": "structured",
  "scoring_type": "dichotomy_weighted_choice",
  "status": "done",
  "started_at": "2026-05-20T09:12:12+00:00",
  "completed_at": "2026-05-20T09:14:10+00:00",
  "responses": [
    {
      "item_id": "mbti_ei_01",
      "axis": "E/I",
      "input_channel": "button",
      "raw_input": "A",
      "resolved_value": "E",
      "confidence": 1.0,
      "resolver_method": "button"
    }
  ],
  "raw_transcripts": [],
  "scores": {
    "raw_scores": {},
    "normalized_scores": {},
    "typology_code": "INTJ",
    "axis_details": {}
  },
  "interpretation": {
    "typology_code": "INTJ",
    "profile": {
      "code": "INTJ",
      "name_ru": "Стратег",
      "tagline": "...",
      "strengths": [],
      "growth_areas": []
    },
    "metadata": {}
  },
  "report": {
    "text_telegram": "=== РЕЗУЛЬТАТ ...",
    "pdf_ref": null
  },
  "dialog_akma": null,
  "audit": {
    "stt_provider": "openai",
    "llm_provider": "openai",
    "engine": "session_engine"
  }
}
```

### Поле `dialog_akma` (только `delivery_mode=dialog`)

```json
{
  "counters": {"EI": 2, "SN": -1, "TF": 0, "JP": 1},
  "type_code": "ENTJ",
  "llm_calls": 14,
  "errors_count": 0
}
```

### Версионирование

- `schema_version` — формат JSON.
- `test_version` — из `TestDefinition.version` (пин на старте сессии).
- Breaking change JSON → `1.1.0`; старые файлы не переписываем.

---

## Точки вставки в коде

```
telegram_adapter.start_test()
  → hr_core.resolve_employee_by_telegram(chat_id)  # client_id, employee_id, display_name
  → SessionEngine / AkmaDialogEngine.start(...)

telegram_adapter._apply_transition()
  → if transition.report_text:
       session_persistence.build_session_result_document(engine, ...)
       session_persistence.persist_session_result(doc)   # if PERSIST_JSON=1
       send Telegram text (как сейчас)
```

Phase 4 заменит `persist_session_result` на INSERT в `pt_test_sessions` без смены формы документа.

---

## hr_core: где что лежит

| Слой | Путь |
|------|------|
| Мастер-данные `Employee.telegram_id` | `app/models.py`, UI сотрудников |
| Мост модуля | `psychological_testing/integration/hr_core.py` |
| Контракт ядра (будущее) | `app.hr.get_employee`, опционально `resolve_by_telegram` |

Не дублировать экран привязки в psych_testing — только читать из HR.

---

## PDF

1. Сохранить JSON (3b).
2. Telegram — текст из `report.text_telegram`.
3. Phase 4: `report_builder` → PDF bytes → `pdf_ref` (путь/URL) + кнопка в workspace / опционально `sendDocument`.

---

## Env (Phase 3b)

```bash
PSYCH_TESTING_PERSIST_JSON=1
# PSYCH_TESTING_SESSIONS_DIR=psychological_testing/data/sessions/v1  # default
PSYCH_TESTING_DEV_CLIENT_ID=dev-client      # fallback если Employee не найден
PSYCH_TESTING_DEV_EMPLOYEE_ID=dev-employee
```

---

## Ссылки

- [08_RBAC_STORAGE_VERSIONING.md](08_RBAC_STORAGE_VERSIONING.md) — целевые `pt_*` таблицы
- [03_MODULAR_STRUCTURE.md](03_MODULAR_STRUCTURE.md) — `integration/hr_core.py`
- [14_E2E_PHASE3_REPORT.md](14_E2E_PHASE3_REPORT.md) — закрытый Telegram E2E
