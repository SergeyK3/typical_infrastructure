# route: /api/onboarding-runs | file: app/routers/onboarding.py

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import OnboardingRun, OnboardingStep
from app.onboarding import compute_payload_hash, run_onboarding_bootstrap
from app.schemas import ListEnvelope, OnboardingRunCreate, OnboardingRunOut, OnboardingRunWithStepsOut

router = APIRouter(prefix="/onboarding-runs", tags=["onboarding"])


@router.get("", response_model=ListEnvelope[OnboardingRunOut])
def list_onboarding_runs(
    db: Session = Depends(get_db),
    client_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[OnboardingRunOut]:
    stmt = select(OnboardingRun)
    if client_id is not None:
        stmt = stmt.where(OnboardingRun.client_id == client_id)
    if status is not None:
        stmt = stmt.where(OnboardingRun.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(OnboardingRun.created_at.desc()).limit(limit).offset(offset)).all()
    return ListEnvelope[OnboardingRunOut](
        items=[OnboardingRunOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=OnboardingRunOut,
    summary="Create onboarding run",
    responses={
        200: {"description": "Run created or existing run returned (idempotent)"},
        400: {"description": "Validation error (e.g. template_not_found)"},
        409: {
            "description": "Conflict: client_code_already_exists, login_already_exists, or idempotency_key_conflict",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "idempotency_key_conflict",
                            "existing_run_id": "run_abc",
                        }
                    }
                }
            },
        },
    },
)
def create_onboarding_run(
    payload: OnboardingRunCreate,
    db: Session = Depends(get_db),
    dry_run: bool = False,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> OnboardingRunOut:
    # Header overrides body for idempotency key (per OpenAPI baseline)
    key = idempotency_key if idempotency_key is not None else payload.idempotency_key
    payload_dict = payload.model_dump()
    if key is not None:
        payload_dict["idempotency_key"] = key
    payload_hash = compute_payload_hash(payload_dict)
    res = run_onboarding_bootstrap(
        db,
        client_code=payload.client.code if payload.client else "",
        client_name=payload.client.name if payload.client else "",
        template_code=payload.template_code,
        action=payload.action,
        existing_client_id=payload.existing_client_id,
        requested_by=payload.requested_by,
        admin_last_name=payload.admin.last_name if payload.admin else "Admin",
        admin_first_name=payload.admin.first_name if payload.admin else "System",
        admin_login=payload.admin.login if payload.admin else "admin",
        admin_password=payload.admin.password if payload.admin else None,
        admin_email=payload.admin.email if payload.admin else None,
        dry_run=dry_run,
        idempotency_key=key,
        payload_hash=payload_hash,
    )
    obj = db.get(OnboardingRun, res.run_id)
    if not obj:
        raise HTTPException(status_code=500, detail="run_not_found_after_create")
    return OnboardingRunOut.model_validate(obj)


@router.get("/{run_id}", response_model=OnboardingRunWithStepsOut)
def get_onboarding_run(run_id: str, db: Session = Depends(get_db)) -> OnboardingRunWithStepsOut:
    run = db.get(OnboardingRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    steps = db.scalars(select(OnboardingStep).where(OnboardingStep.run_id == run_id).order_by(OnboardingStep.created_at.asc())).all()
    return OnboardingRunWithStepsOut(
        run=OnboardingRunOut.model_validate(run),
        steps=[OnboardingRunWithStepsOut.Step.model_validate(s) for s in steps],
    )

