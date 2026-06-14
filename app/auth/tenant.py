"""Tenant-scoped access checks for client-bound API routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.context import CurrentAccount
from app.auth.deps import get_current_account
from app.models import Account, Employee, OrgUnit, Position


def assert_client_access(ctx: CurrentAccount, client_id: str) -> None:
    if not ctx.can_access_client(client_id):
        raise HTTPException(status_code=403, detail="client_access_denied")


def require_client_query_access(
    client_id: str = Query(...),
    ctx: CurrentAccount = Depends(get_current_account),
) -> CurrentAccount:
    assert_client_access(ctx, client_id)
    return ctx


def load_employee_for_ctx(db: Session, employee_id: str, ctx: CurrentAccount) -> Employee:
    emp = db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="employee_not_found")
    assert_client_access(ctx, emp.client_id)
    return emp


def load_org_unit_for_ctx(db: Session, unit_id: str, ctx: CurrentAccount) -> OrgUnit:
    ou = db.get(OrgUnit, unit_id)
    if not ou:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    assert_client_access(ctx, ou.client_id)
    return ou


def load_position_for_ctx(db: Session, position_id: str, ctx: CurrentAccount) -> Position:
    pos = db.get(Position, position_id)
    if not pos:
        raise HTTPException(status_code=404, detail="position_not_found")
    assert_client_access(ctx, pos.client_id)
    return pos


def load_account_for_ctx(db: Session, account_id: str, ctx: CurrentAccount) -> Account:
    obj = db.get(Account, account_id)
    if not obj:
        raise HTTPException(status_code=404, detail="account_not_found")
    if obj.employee_id:
        emp = db.get(Employee, obj.employee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="employee_not_found")
        assert_client_access(ctx, emp.client_id)
    elif not ctx.is_system:
        raise HTTPException(status_code=403, detail="client_access_denied")
    return obj
