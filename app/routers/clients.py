# route: /api/clients | file: app/routers/clients.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, AccountRole, Client, Employee, OrgUnit, Position
from app.schemas import ClientCreate, ClientOut, ClientPatch, ListEnvelope
from app.utils import new_id32

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=ListEnvelope[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[ClientOut]:
    total = db.scalar(select(func.count()).select_from(Client)) or 0
    rows = db.scalars(select(Client).order_by(Client.created_at.desc()).limit(limit).offset(offset)).all()
    return ListEnvelope[ClientOut](
        items=[ClientOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)) -> ClientOut:
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_not_found")
    return ClientOut.model_validate(obj)


@router.post("", response_model=ClientOut)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> ClientOut:
    obj = Client(
        id=payload.id or new_id32(),
        code=payload.code,
        name=payload.name,
        bin=payload.bin,
        status=payload.status,
        template_id=payload.template_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ClientOut.model_validate(obj)


@router.patch("/{client_id}", response_model=ClientOut)
def patch_client(client_id: str, payload: ClientPatch, db: Session = Depends(get_db)) -> ClientOut:
    obj = db.get(Client, client_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_not_found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return ClientOut.model_validate(obj)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str, db: Session = Depends(get_db)) -> Response:
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

