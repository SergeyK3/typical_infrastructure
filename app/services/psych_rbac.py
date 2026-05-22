"""RBAC hooks for psychological testing (Phase 4)."""

from __future__ import annotations

import os

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Employee, Role

PERMISSION_EXPORT = "hr.psych_testing.export"
PERMISSION_ASSIGN = "hr.psych_testing.assign"
PERMISSION_VIEW = "hr.psych_testing.view_team"

HR_ADMIN_ROLE_CODES = frozenset({"admin", "hr_admin", "platform_admin"})


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def export_rbac_enforced() -> bool:
    return _env_enabled("PSYCH_TESTING_RBAC_EXPORT")


def assign_rbac_enforced() -> bool:
    return _env_enabled("PSYCH_TESTING_RBAC_ASSIGN")


def view_rbac_enforced() -> bool:
    return _env_enabled("PSYCH_TESTING_RBAC_VIEW")


def rbac_any_enforced() -> bool:
    return export_rbac_enforced() or assign_rbac_enforced() or view_rbac_enforced()


def rbac_status() -> dict[str, bool]:
    return {
        "rbac_assign_enforced": assign_rbac_enforced(),
        "rbac_view_enforced": view_rbac_enforced(),
        "rbac_export_enforced": export_rbac_enforced(),
    }


def resolve_hr_admin_account_id(db: Session, client_id: str) -> str | None:
    """First active HR-admin account for org (pilot workspace actor)."""
    row = db.execute(
        select(Account.id)
        .join(Employee, Account.employee_id == Employee.id)
        .join(AccountRole, AccountRole.account_id == Account.id)
        .join(Role, Role.id == AccountRole.role_id)
        .where(
            Employee.client_id == client_id,
            Account.status == "active",
            Role.code.in_(HR_ADMIN_ROLE_CODES),
            Role.is_active == True,  # noqa: E712
        )
        .order_by(Account.created_at.asc())
        .limit(1)
    ).first()
    return str(row[0]) if row else None


def _account_role_codes(db: Session, account_id: str) -> set[str]:
    rows = db.execute(
        select(Role.code)
        .join(AccountRole, AccountRole.role_id == Role.id)
        .where(AccountRole.account_id == account_id, Role.is_active == True)  # noqa: E712
    ).all()
    return {str(r[0]) for r in rows}


def _assert_active_account(db: Session, account_id: str | None) -> Account:
    if not account_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "Требуется account_id",
            },
        )
    acc = db.get(Account, account_id)
    if not acc or acc.status != "active":
        raise HTTPException(status_code=403, detail="account_not_found")
    return acc


def _assert_account_client(db: Session, account: Account, client_id: str) -> None:
    actor_emp = db.get(Employee, account.employee_id)
    if actor_emp and str(actor_emp.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail="account_client_mismatch")


def account_has_hr_admin_role(db: Session, account_id: str) -> bool:
    return bool(_account_role_codes(db, account_id) & HR_ADMIN_ROLE_CODES)


def assert_can_export_pdf(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
    employee_id: str | None = None,
) -> None:
    """Enforce ``hr.psych_testing.export`` when ``PSYCH_TESTING_RBAC_EXPORT=1``."""
    if not export_rbac_enforced():
        return
    acc = _assert_active_account(db, account_id)
    if not account_has_hr_admin_role(db, acc.id):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "export_permission_denied",
                "permission": PERMISSION_EXPORT,
                "message": "У аккаунта нет роли для экспорта PDF",
            },
        )
    _assert_account_client(db, acc, client_id)
    if employee_id:
        emp = db.get(Employee, employee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="employee_not_found")
        if str(emp.client_id) != str(client_id):
            raise HTTPException(status_code=403, detail="employee_client_mismatch")


def assert_can_manage_assignments(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
) -> None:
    """Enforce ``hr.psych_testing.assign`` when ``PSYCH_TESTING_RBAC_ASSIGN=1``."""
    if not assign_rbac_enforced():
        return
    acc = _assert_active_account(db, account_id)
    if not account_has_hr_admin_role(db, acc.id):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "assign_permission_denied",
                "permission": PERMISSION_ASSIGN,
                "message": "У аккаунта нет роли для назначения тестов",
            },
        )
    _assert_account_client(db, acc, client_id)


def assert_can_view_psych_data(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
) -> None:
    """Enforce ``hr.psych_testing.view_team`` when ``PSYCH_TESTING_RBAC_VIEW=1``."""
    if not view_rbac_enforced():
        return
    acc = _assert_active_account(db, account_id)
    if not account_has_hr_admin_role(db, acc.id):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "view_permission_denied",
                "permission": PERMISSION_VIEW,
                "message": "У аккаунта нет роли для просмотра результатов",
            },
        )
    _assert_account_client(db, acc, client_id)
