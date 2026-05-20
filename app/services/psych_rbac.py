"""RBAC hooks for psychological testing (Phase E — export)."""

from __future__ import annotations

import os

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Employee, Role

PERMISSION_EXPORT = "hr.psych_testing.export"

# Role codes that may export PDF in v1 (onboarding creates ``admin``).
EXPORT_ROLE_CODES = frozenset({"admin", "hr_admin", "platform_admin"})


def export_rbac_enforced() -> bool:
    return os.getenv("PSYCH_TESTING_RBAC_EXPORT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def account_has_export_permission(db: Session, account_id: str) -> bool:
    rows = db.execute(
        select(Role.code)
        .join(AccountRole, AccountRole.role_id == Role.id)
        .where(AccountRole.account_id == account_id, Role.is_active == True)  # noqa: E712
    ).all()
    codes = {str(r[0]) for r in rows}
    return bool(codes & EXPORT_ROLE_CODES)


def assert_can_export_pdf(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
    employee_id: str | None = None,
) -> None:
    """
    Enforce ``hr.psych_testing.export`` when ``PSYCH_TESTING_RBAC_EXPORT=1``.

    Requires ``account_id`` with role ``admin`` (or hr_admin) and same ``client_id``
    as target employee.
    """
    if not export_rbac_enforced():
        return
    if not account_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "export_permission_denied",
                "message": "Требуется account_id с правом hr.psych_testing.export",
                "permission": PERMISSION_EXPORT,
            },
        )
    acc = db.get(Account, account_id)
    if not acc or acc.status != "active":
        raise HTTPException(status_code=403, detail="account_not_found")
    if not account_has_export_permission(db, account_id):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "export_permission_denied",
                "permission": PERMISSION_EXPORT,
                "message": "У аккаунта нет роли для экспорта PDF",
            },
        )
    if employee_id:
        emp = db.get(Employee, employee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="employee_not_found")
        if str(emp.client_id) != str(client_id):
            raise HTTPException(status_code=403, detail="employee_client_mismatch")
    actor_emp = db.get(Employee, acc.employee_id)
    if actor_emp and str(actor_emp.client_id) != str(client_id):
        raise HTTPException(status_code=403, detail="account_client_mismatch")
