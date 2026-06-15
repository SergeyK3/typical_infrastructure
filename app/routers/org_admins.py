# route: /api/org-admins | file: app/routers/org_admins.py
r"""Organization administrators — accounts with the admin role within a client."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.context import CurrentAccount
from app.auth.deps import get_current_account
from app.auth.tenant import assert_client_access
from app.db import get_db
from app.models import Account, AccountRole, Employee, Role
from app.schemas import ListEnvelope

router = APIRouter(prefix="/org-admins", tags=["org-admins"])


class OrgAdminOut(BaseModel):
    account_id: str
    login: str
    status: str
    employee_id: str
    employee_name: str
    client_id: str


def _employee_display_name(emp: Employee) -> str:
    name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
    return name or emp.email or emp.id


@router.get("", response_model=ListEnvelope[OrgAdminOut])
def list_org_admins(
    client_id: str = Query(..., description="ID организации"),
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[OrgAdminOut]:
    assert_client_access(ctx, client_id)
    admin_role_ids = db.scalars(
        select(Role.id).where(Role.code == "admin", Role.is_active == True)
    ).all()
    if not admin_role_ids:
        return ListEnvelope[OrgAdminOut](items=[], total=0, limit=limit, offset=offset)

    base = (
        select(Account.id)
        .join(Employee, Account.employee_id == Employee.id)
        .join(AccountRole, AccountRole.account_id == Account.id)
        .where(
            Employee.client_id == client_id,
            AccountRole.role_id.in_(admin_role_ids),
        )
        .distinct()
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    q = (
        select(Account, Employee)
        .join(Employee, Account.employee_id == Employee.id)
        .join(AccountRole, AccountRole.account_id == Account.id)
        .where(
            Employee.client_id == client_id,
            AccountRole.role_id.in_(admin_role_ids),
        )
        .distinct()
    )
    rows = db.execute(q.order_by(Account.login).limit(limit).offset(offset)).all()

    items = [
        OrgAdminOut(
            account_id=acc.id,
            login=acc.login,
            status=acc.status,
            employee_id=emp.id,
            employee_name=_employee_display_name(emp),
            client_id=emp.client_id,
        )
        for acc, emp in rows
    ]
    return ListEnvelope[OrgAdminOut](items=items, total=total, limit=limit, offset=offset)
