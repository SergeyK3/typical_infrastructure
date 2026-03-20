# Onboarding Dry-Run Behavior Contract

## 1. Purpose

This document precisely defines which validations are executed in dry-run mode, which steps are marked skipped, the final run status, and how clients should interpret dry-run results.

## 2. When Dry-Run Is Active

- Request includes `dry_run=true` (query param or body option).
- No entities are persisted to the database (clients, org units, positions, employees, accounts).
- A run record and step records are created for observability, but all steps are marked `skipped` except validation.

## 3. Validations Executed

| Validation | Executed in Dry-Run | Notes |
|------------|---------------------|-------|
| Template exists and is active | Yes | `template_code` → `EnterpriseTemplate` lookup |
| Client code uniqueness | Yes | No existing `Client` with same `code` |
| Admin login uniqueness | Yes | No existing `Account` with same `login` |
| Payload structure | Yes | Required fields present, types valid |
| Cross-references (org_unit, position) | Yes | If payload includes custom structure |
| Role existence | Yes | If role codes are specified |

## 4. Steps and Their Status in Dry-Run

| Step Code | Status in Dry-Run | Detail |
|-----------|-------------------|--------|
| validate_request | skipped | dry_run |
| create_client | skipped | dry_run |
| create_root_org_unit | skipped | dry_run |
| deploy_org_units | skipped | dry_run |
| deploy_positions | skipped | dry_run |
| create_admin_employee | skipped | dry_run |
| create_admin_account | skipped | dry_run |
| finalize_run | skipped | dry_run |

All steps start as `pending` and are immediately transitioned to `skipped` with `detail="dry_run"` before any DB writes.

## 5. Run Status for Dry-Run

- **Final run status**: `dry_run`
- **finished_at**: Set immediately after steps are marked skipped.
- **client_id**: `null` (no client created).

## 6. Response Shape

```json
{
  "id": "run_xxx",
  "status": "dry_run",
  "client_id": null,
  "error_code": null,
  "error_message": null,
  "started_at": "2026-03-18T10:00:00Z",
  "finished_at": "2026-03-18T10:00:01Z"
}
```

## 7. Client Interpretation

### 7.1 Success

- `status === "dry_run"` and `error_code === null` → validation passed.
- Client can proceed to a real run (without `dry_run`) using the same or different `idempotency_key`.

### 7.2 Failure

- If validation fails (e.g. `template_not_found`, `client_code_already_exists`, `login_already_exists`), the API returns **4xx** before creating a run.
- No run record is created in that case; client receives the error directly.

### 7.3 Recommended Flow

1. **First**: `POST /onboarding-runs?dry_run=true` with payload.
2. **If 200**: Check `status === "dry_run"` → safe to run for real.
3. **Then**: `POST /onboarding-runs?dry_run=false` with same payload (optionally same `idempotency_key` for traceability).

## 8. Idempotency and Dry-Run

- Dry-run with `idempotency_key` creates a run with `status=dry_run`.
- Retry with same key and `dry_run=true` → returns existing dry-run run (idempotent).
- Retry with same key and `dry_run=false` → if previous was dry-run only, proceeds to real run; if previous was real run, returns existing run.
