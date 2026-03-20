# route: /api/users | file: app/routers/users.py
r"""System-level users (accounts across all clients) — for admin view."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, Client, Employee
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: str
    login: str
    status: str
    client_id: str
    client_name: str
    employee_name: str


class ListEnvelope(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int


@router.get("", response_model=ListEnvelope)
def list_users(
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope:
    """List all system users (accounts) across clients — for admin dashboard."""
    q = (
        select(Account, Client.name.label("client_name"), Employee)
        .join(Employee, Account.employee_id == Employee.id)
        .join(Client, Employee.client_id == Client.id)
    )
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.execute(q.order_by(Account.created_at.desc()).limit(limit).offset(offset)).all()
    items = []
    for acc, client_name, emp in rows:
        name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
        items.append(
            UserOut(
                id=acc.id,
                login=acc.login,
                status=acc.status,
                client_id=emp.client_id,
                client_name=client_name or "",
                employee_name=name or emp.email or "—",
            )
        )
    return ListEnvelope(items=items, total=total, limit=limit, offset=offset)
