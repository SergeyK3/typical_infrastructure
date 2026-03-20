# Onboarding Runs API Reference

## Base Path

`/api/onboarding-runs`

## Endpoints

### `GET /api/onboarding-runs`

List onboarding runs with optional filters.

**Query parameters:**

| Param     | Type   | Default | Description                    |
|-----------|--------|---------|--------------------------------|
| client_id | string | —       | Filter by client ID            |
| status    | string | —       | Filter by run status           |
| limit     | int    | 50      | Page size (1–500)              |
| offset    | int    | 0       | Pagination offset              |

**Response:** `200 OK`

```json
{
  "items": [
    {
      "id": "run_xxx",
      "status": "completed",
      "client_id": "c1",
      "template_id": "t1",
      "requested_by": null,
      "error_code": null,
      "error_message": null,
      "started_at": "2026-03-18T10:00:00Z",
      "finished_at": "2026-03-18T10:01:00Z",
      "created_at": "2026-03-18T10:00:00Z",
      "updated_at": "2026-03-18T10:01:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### `POST /api/onboarding-runs`

Create a new onboarding run (bootstrap enterprise).

**Headers:**

| Header           | Required | Description                                      |
|------------------|----------|--------------------------------------------------|
| Idempotency-Key  | No       | Client-provided key for idempotent retries       |

**Query parameters:**

| Param   | Type | Default | Description                          |
|---------|------|---------|--------------------------------------|
| dry_run | bool | false   | If true, validate only; no DB writes |

**Request body:** `OnboardingRunCreate`

```json
{
  "template_code": "default",
  "requested_by": "operator@example.com",
  "idempotency_key": "req-20260318-001",
  "client": {
    "code": "TOO_ALFA",
    "name": "ТОО Альфа"
  },
  "admin": {
    "last_name": "Admin",
    "first_name": "System",
    "login": "admin",
    "password": "TempPass123!",
    "email": "admin@example.com"
  }
}
```

**Responses:**

- **200 OK** — Run created or existing run returned (idempotent)
- **400 Bad Request** — `template_not_found` or validation error
- **409 Conflict** — `client_code_already_exists`, `login_already_exists`, or `idempotency_key_conflict`

**409 Conflict (idempotency_key_conflict):**

```json
{
  "detail": {
    "code": "idempotency_key_conflict",
    "existing_run_id": "run_abc"
  }
}
```

---

### `GET /api/onboarding-runs/{run_id}`

Get a single run with its steps.

**Response:** `200 OK`

```json
{
  "run": {
    "id": "run_xxx",
    "status": "completed",
    "client_id": "c1",
    "template_id": "t1",
    "requested_by": null,
    "error_code": null,
    "error_message": null,
    "started_at": "2026-03-18T10:00:00Z",
    "finished_at": "2026-03-18T10:01:00Z",
    "created_at": "2026-03-18T10:00:00Z",
    "updated_at": "2026-03-18T10:01:00Z"
  },
  "steps": [
    {
      "id": "step_1",
      "run_id": "run_xxx",
      "step_code": "validate_request",
      "status": "completed",
      "detail": null,
      "started_at": "2026-03-18T10:00:00Z",
      "finished_at": "2026-03-18T10:00:01Z",
      "created_at": "2026-03-18T10:00:00Z",
      "updated_at": "2026-03-18T10:00:01Z"
    }
  ]
}
```

---

## Idempotency

See [onboarding_idempotency_policy.md](./onboarding_idempotency_policy.md).

**Summary:**

- Provide `idempotency_key` (body or `Idempotency-Key` header) for safe retries.
- Same key + same payload → return existing run (200).
- Same key + different payload → 409 Conflict with `existing_run_id`.

---

## Dry-Run

See [onboarding_dry_run_contract.md](./onboarding_dry_run_contract.md).

**Summary:**

- `?dry_run=true` → validation only, no entities created.
- Run status: `dry_run`; all steps: `skipped`.
- Recommended flow: dry-run first, then real run.

---

## Statuses and Error Codes

See [onboarding_statuses_and_error_codes.md](./onboarding_statuses_and_error_codes.md).

**Run statuses:** `pending`, `running`, `completed`, `failed`, `dry_run`

**Step statuses:** `pending`, `running`, `completed`, `failed`, `skipped`

**Error codes:** `client_code_already_exists`, `login_already_exists`, `template_not_found`, `bootstrap_failed`, `idempotency_key_conflict`, etc.

---

## Example Flows

### Retry (same key, same payload)

```
1. POST /api/onboarding-runs
   Body: { idempotency_key: "req-1", client: {...}, admin: {...} }
   → 200, run_id=run_abc, status=running

2. (network timeout, client retries)
   POST /api/onboarding-runs
   Body: { idempotency_key: "req-1", client: {...}, admin: {...} }  # same
   → 200, run_id=run_abc, status=completed  # existing run
```

### Conflict (same key, different payload)

```
1. POST /api/onboarding-runs
   Body: { idempotency_key: "req-1", client: { code: "A" }, ... }
   → 200, run_id=run_abc

2. POST /api/onboarding-runs
   Body: { idempotency_key: "req-1", client: { code: "B" }, ... }  # different
   → 409, detail: { code: "idempotency_key_conflict", existing_run_id: "run_abc" }
```

### Dry-run before real run

```
1. POST /api/onboarding-runs?dry_run=true
   Body: { client: {...}, admin: {...} }
   → 200, status=dry_run, client_id=null

2. POST /api/onboarding-runs?dry_run=false
   Body: { idempotency_key: "req-1", client: {...}, admin: {...} }
   → 200, status=completed, client_id=c1
```
