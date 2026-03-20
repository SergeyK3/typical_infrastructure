# Onboarding Statuses and Error Codes

## 1. OnboardingRun Statuses (Frozen)

| Status | Description |
|--------|-------------|
| `pending` | Run created, not yet started (reserved for future async flow) |
| `running` | Execution in progress |
| `completed` | All steps finished successfully |
| `failed` | One or more steps failed; run stopped |
| `dry_run` | Dry-run completed; no entities created |

### Notes

- `queued`, `partially_completed`, `validated`, `cancelled` are **not** used in current MVP.
- Use `running` → `completed` or `running` → `failed` for real runs.

## 2. OnboardingStep Statuses (Frozen)

| Status | Description |
|--------|-------------|
| `pending` | Step not started |
| `running` | Step in progress |
| `completed` | Step finished successfully |
| `failed` | Step failed |
| `skipped` | Step skipped (e.g. dry-run, conditional skip) |

### Notes

- `done` is **not** used; use `completed` instead.

## 3. Standard Error Codes (OnboardingRun.error_code)

| Code | HTTP | Description |
|------|------|-------------|
| `client_code_already_exists` | 409 | Client with this code already exists |
| `login_already_exists` | 409 | Account login already taken |
| `template_not_found` | 400 | Template code invalid or inactive |
| `bootstrap_failed` | 500 | Generic bootstrap failure (see error_message) |
| `idempotency_key_conflict` | 409 | Same key, different payload |
| `role_admin_not_found` | 500 | Admin role missing in system |
| `missing_parent` | 500 | Org structure reference error |
| `missing_org_unit` | 500 | Position references non-existent org unit |

## 4. API Error Response (detail field)

For 4xx/5xx, `detail` may be a string code (for simple errors) or an object:

```json
{
  "detail": "idempotency_key_conflict",
  "existing_run_id": "run_abc"
}
```
