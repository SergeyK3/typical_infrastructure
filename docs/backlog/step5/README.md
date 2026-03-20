# Step 5 — Backlog tasks (short)

Contract hardening and documentation for onboarding runs.

**Предыдущий шаг:** [Step 4](../step4/README.md) — Onboarding Orchestration (реализация)

См. [BACKLOG_STEPS.md](../BACKLOG_STEPS.md#step-5--backlog-tasks-short) для полного списка задач.

## Документация Step 5

| Документ | Описание |
|----------|----------|
| [onboarding_idempotency_policy.md](../../onboarding/onboarding_idempotency_policy.md) | Политика идемпотентности |
| [onboarding_dry_run_contract.md](../../onboarding/onboarding_dry_run_contract.md) | Контракт dry-run |
| [onboarding_statuses_and_error_codes.md](../../onboarding/onboarding_statuses_and_error_codes.md) | Статусы и коды ошибок |
| [onboarding_api_reference.md](../../onboarding/onboarding_api_reference.md) | API Reference |

## Реализация

- `app/onboarding.py`, `app/models.py`, `app/routers/onboarding.py` — идемпотентность
- `app/onboarding_constants.py` — статусы и error_code
