# route: /api/users | file: app/routers/users.py
r"""System-level users (accounts across all clients) — for admin view."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.context import CurrentAccount
from app.auth.deps import require_global_admin
from app.db import get_db
from app.models import Account, AccountRole, Client, Employee, Role

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: str
    login: str
    status: str
    client_id: str
    client_name: str
    employee_id: str
    employee_name: str
    role_codes: list[str] = Field(default_factory=list)


class ListEnvelope(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int


def _employee_display_name(emp: Employee) -> str:
    name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
    return name or emp.email or emp.id


def _role_codes_for_accounts(db: Session, account_ids: list[str]) -> dict[str, list[str]]:
    if not account_ids:
        return {}
    rows = db.execute(
        select(AccountRole.account_id, Role.code)
        .join(Role, AccountRole.role_id == Role.id)
        .where(AccountRole.account_id.in_(account_ids), Role.is_active == True)
        .order_by(Role.code)
    ).all()
    out: dict[str, list[str]] = {account_id: [] for account_id in account_ids}
    for account_id, code in rows:
        out.setdefault(account_id, []).append(code)
    return out


@router.get("", response_model=ListEnvelope)
def list_users(
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(require_global_admin),
    client_id: str | None = Query(None, description="Filter by organization"),
    role_code: str | None = Query(None, description="Filter by assigned role code"),
    status: str | None = Query(None, description="Filter by account status"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope:
    """List org-bound accounts across clients — Global Admin dashboard."""
    q = (
        select(Account, Client.name.label("client_name"), Employee)
        .join(Employee, Account.employee_id == Employee.id)
        .join(Client, Employee.client_id == Client.id)
    )
    if client_id:
        q = q.where(Employee.client_id == client_id)
    if status:
        q = q.where(Account.status == status)
    if role_code:
        q = (
            q.join(AccountRole, AccountRole.account_id == Account.id)
            .join(Role, AccountRole.role_id == Role.id)
            .where(Role.code == role_code, Role.is_active == True)
            .distinct()
        )

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(q.order_by(Account.created_at.desc()).limit(limit).offset(offset)).all()
    account_ids = [acc.id for acc, _, _ in rows]
    roles_by_account = _role_codes_for_accounts(db, account_ids)

    items = [
        UserOut(
            id=acc.id,
            login=acc.login,
            status=acc.status,
            client_id=emp.client_id,
            client_name=client_name or "",
            employee_id=emp.id,
            employee_name=_employee_display_name(emp),
            role_codes=roles_by_account.get(acc.id, []),
        )
        for acc, client_name, emp in rows
    ]
    return ListEnvelope(items=items, total=total, limit=limit, offset=offset)
