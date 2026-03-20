"""Frozen status and error code constants for onboarding runs and steps."""

# OnboardingRun statuses (frozen for MVP)
RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_DRY_RUN = "dry_run"

RUN_STATUSES = frozenset({
    RUN_STATUS_PENDING,
    RUN_STATUS_RUNNING,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_DRY_RUN,
})

# OnboardingStep statuses (frozen for MVP)
STEP_STATUS_PENDING = "pending"
STEP_STATUS_RUNNING = "running"
STEP_STATUS_COMPLETED = "completed"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_SKIPPED = "skipped"

STEP_STATUSES = frozenset({
    STEP_STATUS_PENDING,
    STEP_STATUS_RUNNING,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_SKIPPED,
})

# Standard error codes for OnboardingRun.error_code
ERROR_CLIENT_CODE_ALREADY_EXISTS = "client_code_already_exists"
ERROR_LOGIN_ALREADY_EXISTS = "login_already_exists"
ERROR_TEMPLATE_NOT_FOUND = "template_not_found"
ERROR_BOOTSTRAP_FAILED = "bootstrap_failed"
ERROR_IDEMPOTENCY_KEY_CONFLICT = "idempotency_key_conflict"
ERROR_ROLE_ADMIN_NOT_FOUND = "role_admin_not_found"
ERROR_MISSING_PARENT = "missing_parent"
ERROR_MISSING_ORG_UNIT = "missing_org_unit"
