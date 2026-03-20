from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException

from app.logging_middleware import get_request_id

logger = logging.getLogger("app.onboarding")
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Client, Employee, EnterpriseTemplate, OnboardingRun, OnboardingStep, OrgUnit, Position, Role
from app.onboarding_constants import (
    ERROR_BOOTSTRAP_FAILED,
    ERROR_CLIENT_CODE_ALREADY_EXISTS,
    ERROR_IDEMPOTENCY_KEY_CONFLICT,
    ERROR_LOGIN_ALREADY_EXISTS,
    ERROR_TEMPLATE_NOT_FOUND,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_DRY_RUN,
    RUN_STATUS_FAILED,
    RUN_STATUS_RUNNING,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_PENDING,
    STEP_STATUS_RUNNING,
    STEP_STATUS_SKIPPED,
)
from app.org_structures import ADMIN_ORG_UNIT_CODE, get_template_positions
from app.template_org_resolve import resolve_template_structure
from app.utils import generate_temp_password, hash_password, new_id32


def compute_payload_hash(payload_dict: dict) -> str:
    """Canonical hash of payload for idempotency conflict detection (excludes idempotency_key)."""
    data = {k: v for k, v in payload_dict.items() if k != "idempotency_key"}
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class BootstrapResult:
    run_id: str
    client_id: str | None
    status: str


def _utcnow() -> datetime:
    return datetime.utcnow()


def _create_step(db: Session, run_id: str, step_code: str) -> OnboardingStep:
    step = OnboardingStep(
        id=new_id32(),
        run_id=run_id,
        step_code=step_code,
        status=STEP_STATUS_PENDING,
    )
    db.add(step)
    db.flush()
    return step


def _start_step(step: OnboardingStep) -> None:
    step.status = STEP_STATUS_RUNNING
    step.started_at = _utcnow()
    logger.info(
        "orchestration_step_start",
        extra={
            "request_id": get_request_id(),
            "run_id": step.run_id,
            "step_code": step.step_code,
            "status": step.status,
        },
    )


def _finish_step(step: OnboardingStep, status: str, detail: str | None = None) -> None:
    step.status = status
    step.detail = detail
    step.finished_at = _utcnow()
    logger.info(
        "orchestration_step_complete",
        extra={
            "request_id": get_request_id(),
            "run_id": step.run_id,
            "step_code": step.step_code,
            "status": status,
            "detail": detail,
        },
    )


def _resolve_existing_run(
    db: Session, idempotency_key: str, payload_hash: str
) -> OnboardingRun | None:
    """Return existing run if same key and payload; raise 409 if key exists with different payload."""
    existing = db.scalar(
        select(OnboardingRun).where(OnboardingRun.idempotency_key == idempotency_key)
    )
    if not existing:
        return None
    if existing.payload_hash != payload_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": ERROR_IDEMPOTENCY_KEY_CONFLICT,
                "message": "Запрос с таким ключом уже выполнен с другими данными.",
                "existing_run_id": existing.id,
            },
        )
    return existing


def run_onboarding_bootstrap(
    db: Session,
    *,
    client_code: str,
    client_name: str,
    template_code: str = "default",
    requested_by: str | None = None,
    admin_last_name: str = "Admin",
    admin_first_name: str = "System",
    admin_login: str = "admin",
    admin_password: str | None = None,
    admin_email: str | None = None,
    dry_run: bool = False,
    idempotency_key: str | None = None,
    payload_hash: str | None = None,
) -> BootstrapResult:
    # Idempotency: if key provided, reuse existing run when payload matches
    if idempotency_key and payload_hash:
        existing = _resolve_existing_run(db, idempotency_key, payload_hash)
        if existing:
            logger.info(
                "orchestration_idempotent_reuse",
                extra={
                    "request_id": get_request_id(),
                    "run_id": existing.id,
                    "status": existing.status,
                },
            )
            return BootstrapResult(
                run_id=existing.id,
                client_id=existing.client_id,
                status=existing.status,
            )

    # Business validation (only when creating new run)
    existing_client = db.scalar(select(Client).where(Client.code == client_code))
    if existing_client:
        raise HTTPException(
            status_code=409,
            detail={"code": ERROR_CLIENT_CODE_ALREADY_EXISTS, "message": "Клиент с таким кодом уже существует."},
        )

    template = db.scalar(select(EnterpriseTemplate).where(EnterpriseTemplate.code == template_code))
    if not template or not template.is_active:
        raise HTTPException(
            status_code=400,
            detail={"code": ERROR_TEMPLATE_NOT_FOUND, "message": "Шаблон предприятия не найден или неактивен."},
        )

    existing_login = db.scalar(select(Account).where(Account.login == admin_login))
    if existing_login:
        raise HTTPException(
            status_code=409,
            detail={"code": ERROR_LOGIN_ALREADY_EXISTS, "message": "Пользователь с таким логином уже существует."},
        )

    run = OnboardingRun(
        id=new_id32(),
        status=RUN_STATUS_RUNNING,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash if idempotency_key else None,
        requested_by=requested_by,
        template_id=template.id,
        started_at=_utcnow(),
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key and payload_hash:
            existing = _resolve_existing_run(db, idempotency_key, payload_hash)
            if existing:
                return BootstrapResult(
                    run_id=existing.id,
                    client_id=existing.client_id,
                    status=existing.status,
                )
        raise

    steps = {
        "validate_request": _create_step(db, run.id, "validate_request"),
        "create_client": _create_step(db, run.id, "create_client"),
        "create_root_org_unit": _create_step(db, run.id, "create_root_org_unit"),
        "deploy_org_units": _create_step(db, run.id, "deploy_org_units"),
        "deploy_positions": _create_step(db, run.id, "deploy_positions"),
        "create_admin_employee": _create_step(db, run.id, "create_admin_employee"),
        "create_admin_account": _create_step(db, run.id, "create_admin_account"),
        "finalize_run": _create_step(db, run.id, "finalize_run"),
    }
    db.commit()

    if dry_run:
        for st in steps.values():
            if st.status == STEP_STATUS_PENDING:
                _finish_step(st, STEP_STATUS_SKIPPED, detail="dry_run")
        run.status = RUN_STATUS_DRY_RUN
        run.finished_at = _utcnow()
        db.commit()
        logger.info(
            "orchestration_dry_run_complete",
            extra={"request_id": get_request_id(), "run_id": run.id, "status": run.status},
        )
        return BootstrapResult(run_id=run.id, client_id=None, status=run.status)

    client_id: str | None = None
    try:
        _start_step(steps["validate_request"])
        _finish_step(steps["validate_request"], STEP_STATUS_COMPLETED)
        db.commit()

        _start_step(steps["create_client"])
        client = Client(
            id=new_id32(),
            code=client_code,
            name=client_name,
            bin=None,
            status="active",
            template_id=template.id,
        )
        db.add(client)
        db.flush()
        client_id = client.id
        run.client_id = client.id
        _finish_step(steps["create_client"], STEP_STATUS_COMPLETED, detail=f"client_id={client.id}")
        db.commit()

        structure = resolve_template_structure(db, template_code)
        ids_by_code: dict[str, str] = {}

        _start_step(steps["create_root_org_unit"])
        root_spec = next(x for x in structure if x["parent_code"] is None)
        root = OrgUnit(
            id=new_id32(),
            client_id=client.id,
            code=root_spec["code"],
            name=root_spec["name"],
            parent_id=None,
            unit_type=root_spec["unit_type"],
            is_active=True,
            sort_order=int(root_spec["sort_order"]),
            catalog_source_code=root_spec["code"],
            is_detached=True,
        )
        db.add(root)
        db.flush()
        ids_by_code[root.code] = root.id
        _finish_step(steps["create_root_org_unit"], STEP_STATUS_COMPLETED, detail=f"org_unit_id={root.id}")
        db.commit()

        _start_step(steps["deploy_org_units"])
        for spec in structure:
            if spec["parent_code"] is None:
                continue
            parent_id = ids_by_code.get(spec["parent_code"])
            if not parent_id:
                raise RuntimeError(f"missing_parent:{spec['parent_code']}")
            ou = OrgUnit(
                id=new_id32(),
                client_id=client.id,
                code=spec["code"],
                name=spec["name"],
                parent_id=parent_id,
                unit_type=spec["unit_type"],
                is_active=True,
                sort_order=int(spec["sort_order"]),
                catalog_source_code=spec["code"],
                is_detached=True,
            )
            db.add(ou)
            db.flush()
            ids_by_code[ou.code] = ou.id
        _finish_step(steps["deploy_org_units"], STEP_STATUS_COMPLETED, detail=f"org_units={len(ids_by_code)}")
        db.commit()

        _start_step(steps["deploy_positions"])
        position_ids: list[str] = []
        for p in get_template_positions(template_code, ids_by_code):
            ou_id = ids_by_code.get(p["org_unit_code"])
            if not ou_id:
                raise RuntimeError(f"missing_org_unit:{p['org_unit_code']}")
            pos = Position(
                id=new_id32(),
                client_id=client.id,
                org_unit_id=ou_id,
                code=p["code"],
                name=p["name"],
                grade=p["grade"],
                is_active=bool(p["is_active"]),
                is_detached=True,
            )
            db.add(pos)
            db.flush()
            position_ids.append(pos.id)
        _finish_step(steps["deploy_positions"], STEP_STATUS_COMPLETED, detail=f"positions={len(position_ids)}")
        db.commit()

        _start_step(steps["create_admin_employee"])
        admin = Employee(
            id=new_id32(),
            client_id=client.id,
            last_name=admin_last_name,
            first_name=admin_first_name,
            middle_name=None,
            email=admin_email,
            phone=None,
            org_unit_id=ids_by_code.get(ADMIN_ORG_UNIT_CODE),
            position_id=None,
            employment_status="active",
            is_manager=True,
        )
        db.add(admin)
        db.flush()
        _finish_step(steps["create_admin_employee"], STEP_STATUS_COMPLETED, detail=f"employee_id={admin.id}")
        db.commit()

        _start_step(steps["create_admin_account"])
        password = admin_password or generate_temp_password()
        password_hash_val = hash_password(password)
        admin_role = db.scalar(select(Role).where(Role.code == "admin", Role.is_active == True))
        if not admin_role:
            raise RuntimeError("role_admin_not_found")
        existing_login = db.scalar(select(Account).where(Account.login == admin_login))
        if existing_login:
            raise HTTPException(
                status_code=409,
                detail={"code": ERROR_LOGIN_ALREADY_EXISTS, "message": "Пользователь с таким логином уже существует."},
            )
        acc = Account(
            id=new_id32(),
            employee_id=admin.id,
            login=admin_login,
            password_hash=password_hash_val,
            status="active",
        )
        db.add(acc)
        db.flush()
        db.add(AccountRole(id=new_id32(), account_id=acc.id, role_id=admin_role.id))
        _finish_step(steps["create_admin_account"], STEP_STATUS_COMPLETED, detail=f"account_id={acc.id}")
        db.commit()

        _start_step(steps["finalize_run"])
        run.status = RUN_STATUS_COMPLETED
        run.finished_at = _utcnow()
        # Traceability: store created entity IDs for run-to-entities mapping
        created_entities = {
            "client_id": client_id,
            "org_unit_ids": list(ids_by_code.values()),
            "position_ids": position_ids,
            "employee_id": admin.id,
            "account_id": acc.id,
        }
        run.created_entities = json.dumps(created_entities)
        _finish_step(steps["finalize_run"], STEP_STATUS_COMPLETED)
        db.commit()

        logger.info(
            "orchestration_complete",
            extra={
                "request_id": get_request_id(),
                "run_id": run.id,
                "status": run.status,
                "client_id": client_id,
            },
        )
        return BootstrapResult(run_id=run.id, client_id=client_id, status=run.status)
    except Exception as e:  # noqa: BLE001
        run.status = RUN_STATUS_FAILED
        run.error_code = ERROR_BOOTSTRAP_FAILED
        run.error_message = str(e)
        run.finished_at = _utcnow()
        logger.warning(
            "orchestration_failed",
            extra={
                "request_id": get_request_id(),
                "run_id": run.id,
                "status": run.status,
                "error_code": run.error_code,
                "error_message": run.error_message,
            },
        )
        try:
            for st in steps.values():
                if st.status == STEP_STATUS_RUNNING:
                    _finish_step(st, STEP_STATUS_FAILED, detail=run.error_message)
        finally:
            db.commit()
        raise
