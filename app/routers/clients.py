# route: /api/clients | file: app/routers/clients.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_account, require_client_access, require_system_admin
from app.auth.context import CurrentAccount
from app.db import get_db
from app.models import Account, AccountRole, Client, Employee, EnterpriseTemplate, OrgUnit, Position
from app.schemas import ClientCreate, ClientOut, ClientPatch, ListEnvelope
from app.utils import new_id32

router = APIRouter(prefix="/clients", tags=["clients"])


def _resolve_template_id(db: Session, template_code: str) -> str:
    code = template_code.strip()
    tpl = db.scalar(
        select(EnterpriseTemplate).where(
            EnterpriseTemplate.code == code,
            EnterpriseTemplate.is_active == True,
        )
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="template_not_found")
    return tpl.id


def _client_out(db: Session, obj: Client) -> ClientOut:
    template_code: str | None = None
    if obj.template_id:
        tpl = db.get(EnterpriseTemplate, obj.template_id)
        template_code = tpl.code if tpl else None
    return ClientOut.model_validate(obj).model_copy(update={"template_code": template_code})


@router.get("", response_model=ListEnvelope[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(get_current_account),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[ClientOut]:
    if not ctx.is_system:
        if not ctx.allowed_clients:
            return ListEnvelope[ClientOut](items=[], total=0, limit=limit, offset=offset)
        base = select(Client).where(Client.id.in_(ctx.allowed_clients))
    else:
        base = select(Client)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Client.created_at.desc()).limit(limit).offset(offset)).all()
    return ListEnvelope[ClientOut](
        items=[_client_out(db, r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    ctx: CurrentAccount = Depends(require_client_access),
) -> ClientOut:
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_not_found")
    return _client_out(db, obj)


@router.post("", response_model=ClientOut)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(require_system_admin),
) -> ClientOut:
    template_id = payload.template_id
    if payload.template_code and not template_id:
        template_id = _resolve_template_id(db, payload.template_code)
    obj = Client(
        id=payload.id or new_id32(),
        code=payload.code,
        name=payload.name,
        short_name=(payload.short_name or "").strip() or None,
        bin=payload.bin,
        status=payload.status,
        template_id=template_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _client_out(db, obj)


@router.patch("/{client_id}", response_model=ClientOut)
def patch_client(
    client_id: str,
    payload: ClientPatch,
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(require_system_admin),
) -> ClientOut:
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_not_found")
    data = payload.model_dump(exclude_unset=True)
    template_code = data.pop("template_code", None)
    if template_code is not None:
        data["template_id"] = _resolve_template_id(db, template_code)
    if "short_name" in data:
        raw = data["short_name"]
        data["short_name"] = (raw or "").strip() or None if raw is not None else None
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _client_out(db, obj)


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    _ctx: CurrentAccount = Depends(require_system_admin),
) -> Response:
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_not_found")
    employees = db.scalars(select(Employee).where(Employee.client_id == client_id)).all()
    for emp in employees:
        acc = db.scalar(select(Account).where(Account.employee_id == emp.id))
        if acc:
            for ar in db.scalars(select(AccountRole).where(AccountRole.account_id == acc.id)).all():
                db.delete(ar)
            db.delete(acc)
        db.delete(emp)
    for pos in db.scalars(select(Position).where(Position.client_id == client_id)).all():
        db.delete(pos)
    for ou in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all():
        db.delete(ou)
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
