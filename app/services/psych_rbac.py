"""RBAC hooks for psychological testing (Phase 4)."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Employee, Role

PERMISSION_EXPORT = "hr.psych_testing.export"
PERMISSION_ASSIGN = "hr.psych_testing.assign"
PERMISSION_VIEW = "hr.psych_testing.view_team"

HR_ADMIN_ROLE_CODES = frozenset({"admin", "hr_admin", "platform_admin"})
MANAGER_ROLE_CODES = frozenset({"manager"})

PsychViewScope = Literal["all_org", "team", "none"]


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


def _account_role_codes(db: Session, account_id: str) -> set[str]:
    rows = db.execute(
        select(Role.code)
        .join(AccountRole, AccountRole.role_id == Role.id)
        .where(AccountRole.account_id == account_id, Role.is_active == True)  # noqa: E712
    ).all()
    return {str(r[0]) for r in rows}


def account_has_hr_admin_role(db: Session, account_id: str) -> bool:
    return bool(_account_role_codes(db, account_id) & HR_ADMIN_ROLE_CODES)


def account_has_manager_role(db: Session, account_id: str) -> bool:
    return bool(_account_role_codes(db, account_id) & MANAGER_ROLE_CODES)


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


def direct_report_employee_ids(
    db: Session,
    *,
    client_id: str,
    manager_employee_id: str,
) -> frozenset[str]:
    """
    Direct reports for manager RBAC.

    1. Employees with ``manager_employee_id`` pointing to the manager (if column set).
    2. Else: same ``org_unit_id`` as manager (department-scoped), excluding self.
    """
    mgr = db.get(Employee, manager_employee_id)
    if mgr is None or str(mgr.client_id) != str(client_id):
        return frozenset()

    explicit: set[str] = set()
    for emp in db.scalars(select(Employee).where(Employee.client_id == client_id)).all():
        if str(emp.id) == str(manager_employee_id):
            continue
        mid = getattr(emp, "manager_employee_id", None)
        if mid and str(mid) == str(manager_employee_id):
            explicit.add(str(emp.id))
    if explicit:
        return frozenset(explicit)

    if not mgr.org_unit_id:
        return frozenset()
    team: set[str] = set()
    for emp in db.scalars(
        select(Employee).where(
            Employee.client_id == client_id,
            Employee.org_unit_id == mgr.org_unit_id,
            Employee.id != manager_employee_id,
        )
    ).all():
        team.add(str(emp.id))
    return frozenset(team)


def view_scope_for_account(
    db: Session,
    *,
    account_id: str,
    client_id: str,
) -> PsychViewScope:
    if account_has_hr_admin_role(db, account_id):
        return "all_org"
    if account_has_manager_role(db, account_id):
        return "team"
    return "none"


def visible_employee_ids_for_view(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
) -> frozenset[str] | None:
    """
    ``None`` — no employee filter (all org or RBAC off).
    Empty frozenset — no visible employees.
    """
    if not view_rbac_enforced():
        return None
    acc = _assert_active_account(db, account_id)
    _assert_account_client(db, acc, client_id)
    scope = view_scope_for_account(db, account_id=acc.id, client_id=client_id)
    if scope == "all_org":
        return None
    if scope == "team":
        return direct_report_employee_ids(db, client_id=client_id, manager_employee_id=acc.employee_id)
    return frozenset()


def permissions_for_account(
    db: Session,
    *,
    account_id: str,
    client_id: str,
) -> dict[str, bool | str]:
    """Effective psych-testing permissions for UI / API context."""
    is_admin = account_has_hr_admin_role(db, account_id)
    is_manager = account_has_manager_role(db, account_id)
    scope = view_scope_for_account(db, account_id=account_id, client_id=client_id)

    if not rbac_any_enforced():
        return {
            "scope": "all_org",
            "is_hr_admin": is_admin,
            "is_manager": is_manager,
            "can_view": True,
            "can_assign": True,
            "can_export": True,
        }

    can_view = (is_admin or is_manager) if view_rbac_enforced() else True
    can_assign = is_admin if assign_rbac_enforced() else True
    can_export = is_admin if export_rbac_enforced() else True
    return {
        "scope": scope,
        "is_hr_admin": is_admin,
        "is_manager": is_manager,
        "can_view": can_view,
        "can_assign": can_assign,
        "can_export": can_export,
    }


def build_rbac_context(db: Session, *, client_id: str) -> dict:
    """Workspace context: HR admin account + effective permissions."""
    flags = rbac_status()
    workspace_account_id = (
        resolve_hr_admin_account_id(db, client_id) if rbac_any_enforced() else None
    )
    perms: dict[str, bool | str] = {
        "scope": "all_org",
        "is_hr_admin": False,
        "is_manager": False,
        "can_view": True,
        "can_assign": True,
        "can_export": True,
    }
    if workspace_account_id:
        perms = permissions_for_account(db, account_id=workspace_account_id, client_id=client_id)
    return {
        **flags,
        "hr_admin_account_id": workspace_account_id,
        "workspace_account_id": workspace_account_id,
        **perms,
    }


def assert_can_export_pdf(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
    employee_id: str | None = None,
) -> None:
    """Enforce ``hr.psych_testing.export`` when ``PSYCH_TESTING_RBAC_EXPORT=1`` (HR admin only)."""
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
    """Enforce ``hr.psych_testing.assign`` when ``PSYCH_TESTING_RBAC_ASSIGN=1`` (HR admin only)."""
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
    """Enforce view permission: HR admin (all org) or manager (team) when RBAC view is on."""
    if not view_rbac_enforced():
        return
    acc = _assert_active_account(db, account_id)
    _assert_account_client(db, acc, client_id)
    if not (account_has_hr_admin_role(db, acc.id) or account_has_manager_role(db, acc.id)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "view_permission_denied",
                "permission": PERMISSION_VIEW,
                "message": "У аккаунта нет роли для просмотра результатов",
            },
        )


def assert_can_view_employee_psych_data(
    db: Session,
    *,
    account_id: str | None,
    client_id: str,
    employee_id: str,
) -> None:
    """View gate + team scope (manager sees direct reports only)."""
    assert_can_view_psych_data(db, account_id=account_id, client_id=client_id)
    visible = visible_employee_ids_for_view(
        db, account_id=account_id, client_id=client_id
    )
    if visible is None:
        return
    if str(employee_id) not in visible:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "view_scope_denied",
                "permission": PERMISSION_VIEW,
                "message": "Нет доступа к результатам этого сотрудника",
            },
        )
