# Onboarding Idempotency Policy

## 1. Purpose

This document defines the semantics of `idempotency_key` for onboarding runs, allowed retry scenarios per run status, and expected API behavior on duplicate keys.

## 2. Idempotency Key Semantics

### 2.1 Definition

- **idempotency_key**: An optional client-provided string (max 64 chars) that uniquely identifies a logical onboarding request.
- **Source**: Passed in the request body (`idempotency_key`) or via `Idempotency-Key` header (if supported).
- **Scope**: One key maps to at most one successful onboarding run for the same logical operation.

### 2.2 When Provided

- If `idempotency_key` is provided and a run with that key already exists, the API **reuses** the existing run instead of creating a new one.
- The response returns the existing run's data (same `run_id`, status, etc.).
- No duplicate entities (clients, org units, accounts) are created.

### 2.3 When Not Provided

- Each request creates a new run.
- Retries without a key result in duplicate runs and may fail on business constraints (e.g. `client_code_already_exists`).

## 3. Retry Scenarios by Run Status

| Run Status   | Retry with same key | API Behavior |
|-------------|---------------------|--------------|
| **pending** | Yes                 | Return existing run (200). Run may still be queued. |
| **running** | Yes                 | Return existing run (200). Client should poll for completion. |
| **completed** | Yes               | Return existing run (200). Idempotent success — no new work. |
| **failed**  | Yes                 | Return existing run (200). Client receives the failed run; may retry with a **new** key if they fix the payload. |
| **dry_run** | Yes                 | Return existing run (200). Dry-run result is cached; client can proceed to real run with same or new key. |

### 3.1 Conflict (409)

- **Payload mismatch**: If the same `idempotency_key` is used with a **different** payload (e.g. different `client_code`, `template_code`, admin data), the API returns **409 Conflict**.
- **Reason**: Prevents accidental overwrite or inconsistent state.
- **Client action**: Use a new key for the new payload, or resolve the conflict explicitly.

## 4. Expected API Behavior

### 4.1 Success Path (Reuse)

```
Request: POST /api/v1/onboarding-runs
Body: { idempotency_key: "req-123", client: {...}, ... }

Response: 200 OK
Body: { id: "run_abc", status: "completed", client_id: "c1", ... }
```

- Same key, same payload → return existing run.

### 4.2 Conflict Path

```
Request: POST /api/v1/onboarding-runs
Body: { idempotency_key: "req-123", client: { code: "OTHER" }, ... }
       (different payload than original)

Response: 409 Conflict
Body: { detail: "idempotency_key_conflict", existing_run_id: "run_abc" }
```

### 4.3 New Run Path

```
Request: POST /api/v1/onboarding-runs
Body: { idempotency_key: "req-456", client: {...}, ... }
       (new key or no key)

Response: 200 OK (or 201 Created)
Body: { id: "run_xyz", status: "running", ... }
```

## 5. Payload Comparison

- For conflict detection, the backend compares a **payload hash** of the request body (excluding `idempotency_key`).
- If hash matches → reuse.
- If hash differs → 409 Conflict.

## 6. Concurrency

- **Unique index**: `onboarding_runs.idempotency_key` has a unique partial index (WHERE idempotency_key IS NOT NULL).
- **Concurrent requests**: Two requests with the same key arriving simultaneously:
  - First insert wins.
  - Second gets unique constraint violation → retry logic or return 409 with `existing_run_id`.
