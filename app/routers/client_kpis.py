# route: /api/client-kpis | file: app/routers/client_kpis.py
r"""Локальные KPI организации без привязки к регламенту."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, ClientStandaloneKpi
from app.schemas import ClientStandaloneKpiCreate, ClientStandaloneKpiOut, ClientStandaloneKpiPatch, ListEnvelope
from app.utils import new_id32

router = APIRouter(prefix="/client-kpis", tags=["client-kpis"])


def _assert_client(db: Session, client_id: str) -> None:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")


@router.get("", response_model=ListEnvelope[ClientStandaloneKpiOut])
def list_client_standalone_kpis(
    client_id: str = Query(..., description="ID организации"),
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[ClientStandaloneKpiOut]:
    _assert_client(db, client_id)
    q = select(ClientStandaloneKpi).where(ClientStandaloneKpi.client_id == client_id)
    total = db.scalar(
        select(func.count())
        .select_from(ClientStandaloneKpi)
        .where(ClientStandaloneKpi.client_id == client_id)
    ) or 0
    rows = db.scalars(q.order_by(ClientStandaloneKpi.kpi_code).limit(limit).offset(offset)).all()
    return ListEnvelope[ClientStandaloneKpiOut](
        items=[ClientStandaloneKpiOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ClientStandaloneKpiOut, status_code=201)
def create_client_standalone_kpi(
    body: ClientStandaloneKpiCreate, db: Session = Depends(get_db)
) -> ClientStandaloneKpiOut:
    _assert_client(db, body.client_id)
    code = body.kpi_code.strip()
    dup = db.scalar(
        select(ClientStandaloneKpi).where(
            ClientStandaloneKpi.client_id == body.client_id,
            ClientStandaloneKpi.kpi_code == code,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail="client_standalone_kpi_exists")
    obj = ClientStandaloneKpi(
        id=new_id32(),
        client_id=body.client_id,
        kpi_code=code,
        target_value=body.target_value,
        period_type=body.period_type,
        weight=body.weight,
        is_required=body.is_required,
        position_code=body.position_code,
        notes=body.notes,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ClientStandaloneKpiOut.model_validate(obj)


@router.patch("/{kpi_id}", response_model=ClientStandaloneKpiOut)
def patch_client_standalone_kpi(
    kpi_id: str, body: ClientStandaloneKpiPatch, db: Session = Depends(get_db)
) -> ClientStandaloneKpiOut:
    obj = db.get(ClientStandaloneKpi, kpi_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_standalone_kpi_not_found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return ClientStandaloneKpiOut.model_validate(obj)


@router.delete("/{kpi_id}", status_code=204)
def delete_client_standalone_kpi(kpi_id: str, db: Session = Depends(get_db)) -> Response:
    obj = db.get(ClientStandaloneKpi, kpi_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_standalone_kpi_not_found")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
