# route: /api/client-kpis | file: app/routers/client_kpis.py
r"""Локальные KPI организации без привязки к регламенту."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import (
    Client,
    ClientPositionRegulation,
    ClientRegulationKpi,
    ClientStandaloneKpi,
)
from app.schemas import ClientStandaloneKpiCreate, ClientStandaloneKpiOut, ClientStandaloneKpiPatch, ListEnvelope
from app.utils import new_id32

router = APIRouter(prefix="/client-kpis", tags=["client-kpis"])


def _assert_client(db: Session, client_id: str) -> None:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")


@router.get("/export/excel")
def export_local_kpis_excel(
    client_id: str = Query(..., description="ID организации"),
    db: Session = Depends(get_db),
) -> Response:
    """Сводная выгрузка KPI организации: из локальных регламентов и без регламента."""
    _assert_client(db, client_id)
    headers = [
        "kpi_code",
        "position_code",
        "dept_type_code",
        "target_value",
        "period_type",
        "weight",
        "is_active",
        "regulation_code",
        "regulation_name",
        "from_regulation",
        "kpi_id",
    ]
    data: list[list] = []
    regs = db.scalars(
        select(ClientPositionRegulation)
        .where(ClientPositionRegulation.client_id == client_id)
        .order_by(
            ClientPositionRegulation.position_code,
            ClientPositionRegulation.dept_type_code,
            ClientPositionRegulation.regulation_code,
        )
    ).all()
    for reg in regs:
        kpis = db.scalars(
            select(ClientRegulationKpi).where(
                ClientRegulationKpi.client_regulation_id == reg.id
            )
        ).all()
        for kpi in kpis:
            data.append(
                [
                    kpi.kpi_code,
                    reg.position_code,
                    reg.dept_type_code,
                    kpi.target_value,
                    kpi.period_type,
                    kpi.weight,
                    kpi.is_active,
                    reg.regulation_code,
                    reg.regulation_name,
                    True,
                    kpi.id,
                ]
            )
    standalone = db.scalars(
        select(ClientStandaloneKpi)
        .where(ClientStandaloneKpi.client_id == client_id)
        .order_by(ClientStandaloneKpi.kpi_code)
    ).all()
    for kpi in standalone:
        data.append(
            [
                kpi.kpi_code,
                kpi.position_code,
                None,
                kpi.target_value,
                kpi.period_type,
                kpi.weight,
                kpi.is_active,
                None,
                None,
                False,
                kpi.id,
            ]
        )
    return xlsx_file_response(
        download_name=f"local_kpis_{client_id}.xlsx",
        sheet_title="local_kpis",
        headers=headers,
        rows=data,
    )


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
        is_active=body.is_active,
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
