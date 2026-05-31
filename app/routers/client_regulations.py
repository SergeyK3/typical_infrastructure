# route: /api/client-regulations | file: app/routers/client_regulations.py
r"""Клиентские копии регламентов должностей (по organization / client_id)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.template_bundle_clone import resolve_client_template_code
from app.excel_export import xlsx_file_response
from app.models import (
    Client,
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)
from app.schemas import (
    ClientPositionRegulationCopyFromGlobal,
    ClientPositionRegulationCreate,
    ClientPositionRegulationDetailOut,
    ClientPositionRegulationOut,
    ClientPositionRegulationPatch,
    ClientRegulationInstructionIn,
    ClientRegulationInstructionOut,
    ClientRegulationKpiIn,
    ClientRegulationKpiOut,
    ListEnvelope,
)
from app.utils import new_id32

router = APIRouter(prefix="/client-regulations", tags=["client-regulations"])


def _assert_client(db: Session, client_id: str) -> None:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")


def _ilike_client_reg_search(raw: str):
    frag = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pat = f"%{frag}%"
    return or_(
        ClientPositionRegulation.regulation_code.ilike(pat, escape="\\"),
        ClientPositionRegulation.regulation_name.ilike(pat, escape="\\"),
        ClientPositionRegulation.position_code.ilike(pat, escape="\\"),
        ClientPositionRegulation.dept_type_code.ilike(pat, escape="\\"),
        func.coalesce(ClientPositionRegulation.global_regulation_code, "").ilike(pat, escape="\\"),
        func.coalesce(ClientPositionRegulation.goal_summary, "").ilike(pat, escape="\\"),
        func.coalesce(ClientPositionRegulation.notes, "").ilike(pat, escape="\\"),
    )


def _load_detail(db: Session, reg_id: str) -> ClientPositionRegulationDetailOut:
    obj = db.get(ClientPositionRegulation, reg_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_regulation_not_found")
    kpis = db.scalars(
        select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == reg_id)
    ).all()
    instr = db.scalars(
        select(ClientRegulationInstruction)
        .where(ClientRegulationInstruction.client_regulation_id == reg_id)
        .order_by(ClientRegulationInstruction.sort_order)
    ).all()
    return ClientPositionRegulationDetailOut(
        **ClientPositionRegulationOut.model_validate(obj).model_dump(),
        kpis=[ClientRegulationKpiOut.model_validate(k) for k in kpis],
        instructions=[ClientRegulationInstructionOut.model_validate(i) for i in instr],
    )


def _insert_children(
    db: Session,
    reg_id: str,
    kpis: list[ClientRegulationKpiIn],
    instructions: list[ClientRegulationInstructionIn],
) -> None:
    for k in kpis:
        db.add(
            ClientRegulationKpi(
                id=new_id32(),
                client_regulation_id=reg_id,
                kpi_code=k.kpi_code,
                target_value=k.target_value,
                period_type=k.period_type,
                weight=k.weight,
                is_required=k.is_required,
                is_active=k.is_active,
            )
        )
    for ins in instructions:
        db.add(
            ClientRegulationInstruction(
                id=new_id32(),
                client_regulation_id=reg_id,
                instruction_code=ins.instruction_code,
                instruction_name=ins.instruction_name,
                instruction_url=ins.instruction_url,
                is_required=ins.is_required,
                sort_order=ins.sort_order,
            )
        )


@router.get("", response_model=ListEnvelope[ClientPositionRegulationOut])
def list_client_regulations(
    client_id: str = Query(..., description="ID организации"),
    search: str | None = Query(None, max_length=200),
    position_code: str | None = Query(None, max_length=64),
    dept_type_code: str | None = Query(None, max_length=32),
    status: str | None = Query(None, max_length=16),
    is_current: bool | None = Query(None, description="Только действующие, если true"),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[ClientPositionRegulationOut]:
    _assert_client(db, client_id)
    filters = [ClientPositionRegulation.client_id == client_id]
    if search and (s := search.strip()):
        filters.append(_ilike_client_reg_search(s))
    if position_code:
        filters.append(ClientPositionRegulation.position_code == position_code)
    if dept_type_code:
        filters.append(ClientPositionRegulation.dept_type_code == dept_type_code)
    if status:
        filters.append(ClientPositionRegulation.status == status)
    if is_current is not None:
        filters.append(ClientPositionRegulation.is_current == is_current)
    q = select(ClientPositionRegulation)
    count_q = select(func.count()).select_from(ClientPositionRegulation)
    for f in filters:
        q = q.where(f)
        count_q = count_q.where(f)
    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(
            ClientPositionRegulation.position_code,
            ClientPositionRegulation.dept_type_code,
            ClientPositionRegulation.version_no,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return ListEnvelope[ClientPositionRegulationOut](
        items=[ClientPositionRegulationOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export/excel")
def export_client_regulations_excel(
    client_id: str = Query(..., description="ID организации"),
    search: str | None = Query(None, max_length=200),
    position_code: str | None = Query(None, max_length=64),
    dept_type_code: str | None = Query(None, max_length=32),
    status: str | None = Query(None, max_length=16),
    is_current: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    _assert_client(db, client_id)
    filters = [ClientPositionRegulation.client_id == client_id]
    if search and (s := search.strip()):
        filters.append(_ilike_client_reg_search(s))
    if position_code:
        filters.append(ClientPositionRegulation.position_code == position_code)
    if dept_type_code:
        filters.append(ClientPositionRegulation.dept_type_code == dept_type_code)
    if status:
        filters.append(ClientPositionRegulation.status == status)
    if is_current is not None:
        filters.append(ClientPositionRegulation.is_current == is_current)
    q = select(ClientPositionRegulation)
    for f in filters:
        q = q.where(f)
    rows = db.scalars(
        q.order_by(
            ClientPositionRegulation.position_code,
            ClientPositionRegulation.dept_type_code,
            ClientPositionRegulation.version_no,
        ).limit(5000)
    ).all()
    headers = [
        "id",
        "client_id",
        "regulation_code",
        "global_regulation_code",
        "is_detached",
        "position_code",
        "dept_type_code",
        "regulation_name",
        "goal_summary",
        "ckp_short",
        "ckp_full",
        "google_doc_url",
        "instructions_folder_url",
        "version_no",
        "status",
        "effective_from",
        "effective_to",
        "is_current",
        "owner_unit_code",
        "notes",
        "created_at",
        "updated_at",
    ]
    data = []
    for r in rows:
        o = ClientPositionRegulationOut.model_validate(r)
        data.append(
            [
                o.id,
                o.client_id,
                o.regulation_code,
                o.global_regulation_code,
                o.is_detached,
                o.position_code,
                o.dept_type_code,
                o.regulation_name,
                o.goal_summary,
                o.ckp_short,
                o.ckp_full,
                o.google_doc_url,
                o.instructions_folder_url,
                o.version_no,
                o.status,
                o.effective_from,
                o.effective_to,
                o.is_current,
                o.owner_unit_code,
                o.notes,
                o.created_at,
                o.updated_at,
            ]
        )
    return xlsx_file_response(
        download_name=f"client_regulations_{client_id}.xlsx",
        sheet_title="client_regulations",
        headers=headers,
        rows=data,
    )


@router.get("/{regulation_id}", response_model=ClientPositionRegulationDetailOut)
def get_client_regulation(regulation_id: str, db: Session = Depends(get_db)) -> ClientPositionRegulationDetailOut:
    return _load_detail(db, regulation_id)


@router.post("", response_model=ClientPositionRegulationDetailOut, status_code=201)
def create_client_regulation(
    body: ClientPositionRegulationCreate, db: Session = Depends(get_db)
) -> ClientPositionRegulationDetailOut:
    _assert_client(db, body.client_id)
    dup = db.scalar(
        select(ClientPositionRegulation).where(
            ClientPositionRegulation.client_id == body.client_id,
            ClientPositionRegulation.regulation_code == body.regulation_code,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail="client_regulation_code_exists")
    rid = body.id or new_id32()
    obj = ClientPositionRegulation(
        id=rid,
        client_id=body.client_id,
        regulation_code=body.regulation_code,
        global_regulation_code=body.global_regulation_code,
        is_detached=body.is_detached,
        position_code=body.position_code,
        dept_type_code=body.dept_type_code,
        regulation_name=body.regulation_name,
        goal_summary=body.goal_summary,
        ckp_short=body.ckp_short,
        ckp_full=body.ckp_full,
        google_doc_url=body.google_doc_url,
        instructions_folder_url=body.instructions_folder_url,
        version_no=body.version_no,
        status=body.status,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_current=body.is_current,
        owner_unit_code=body.owner_unit_code,
        notes=body.notes,
    )
    db.add(obj)
    db.flush()
    _insert_children(db, rid, body.kpis, body.instructions)
    db.commit()
    db.refresh(obj)
    return _load_detail(db, rid)


@router.post("/copy-from-global", response_model=ClientPositionRegulationDetailOut)
def copy_regulation_from_global(
    body: ClientPositionRegulationCopyFromGlobal, response: Response, db: Session = Depends(get_db)
) -> ClientPositionRegulationDetailOut:
    _assert_client(db, body.client_id)
    tpl_code = resolve_client_template_code(db, body.client_id)
    glob = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == tpl_code,
            PositionRegulation.regulation_code == body.global_regulation_code,
        )
    )
    if not glob:
        raise HTTPException(status_code=404, detail="global_regulation_not_found")
    target_code = (body.regulation_code or body.global_regulation_code).strip()
    existing = db.scalar(
        select(ClientPositionRegulation).where(
            ClientPositionRegulation.client_id == body.client_id,
            ClientPositionRegulation.global_regulation_code == body.global_regulation_code,
        )
    )
    if not existing:
        existing = db.scalar(
            select(ClientPositionRegulation).where(
                ClientPositionRegulation.client_id == body.client_id,
                ClientPositionRegulation.regulation_code == target_code,
            )
        )
    if existing:
        from app.client_catalog_sync import sync_client_regulation_children_from_global

        sync_client_regulation_children_from_global(db, existing.id)
        db.commit()
        response.status_code = 200
        return _load_detail(db, existing.id)
    rid = new_id32()
    obj = ClientPositionRegulation(
        id=rid,
        client_id=body.client_id,
        regulation_code=target_code,
        global_regulation_code=body.global_regulation_code,
        is_detached=True,
        position_code=glob.position_code,
        dept_type_code=glob.dept_type_code,
        regulation_name=glob.regulation_name,
        goal_summary=glob.goal_summary,
        ckp_short=glob.ckp_short,
        ckp_full=glob.ckp_full,
        google_doc_url=glob.google_doc_url,
        instructions_folder_url=glob.instructions_folder_url,
        version_no=glob.version_no,
        status=glob.status,
        effective_from=glob.effective_from,
        effective_to=glob.effective_to,
        is_current=glob.is_current,
        owner_unit_code=glob.owner_unit_code,
        notes=glob.notes,
    )
    db.add(obj)
    db.flush()
    for k in db.scalars(
        select(RegulationKpi).where(
            RegulationKpi.template_code == glob.template_code,
            RegulationKpi.regulation_code == body.global_regulation_code,
        )
    ).all():
        db.add(
            ClientRegulationKpi(
                id=new_id32(),
                client_regulation_id=rid,
                kpi_code=k.kpi_code,
                target_value=k.target_value,
                period_type=k.period_type,
                weight=k.weight,
                is_required=k.is_required,
                is_active=k.is_active,
            )
        )
    for ins in db.scalars(
        select(RegulationInstruction)
        .where(
            RegulationInstruction.template_code == glob.template_code,
            RegulationInstruction.regulation_code == body.global_regulation_code,
        )
        .order_by(RegulationInstruction.sort_order)
    ).all():
        db.add(
            ClientRegulationInstruction(
                id=new_id32(),
                client_regulation_id=rid,
                instruction_code=ins.instruction_code,
                instruction_name=ins.instruction_name,
                instruction_url=ins.instruction_url,
                is_required=ins.is_required,
                sort_order=ins.sort_order,
            )
        )
    db.commit()
    db.refresh(obj)
    response.status_code = 201
    return _load_detail(db, rid)


@router.post("/{regulation_id}/sync-from-global")
def sync_client_regulation_from_global(regulation_id: str, db: Session = Depends(get_db)) -> dict:
    from app.client_catalog_sync import sync_client_regulation_children_from_global

    kpis, instructions = sync_client_regulation_children_from_global(db, regulation_id)
    db.commit()
    return {"kpis_added": kpis, "instructions_added": instructions}


@router.patch("/{regulation_id}", response_model=ClientPositionRegulationDetailOut)
def patch_client_regulation(
    regulation_id: str, body: ClientPositionRegulationPatch, db: Session = Depends(get_db)
) -> ClientPositionRegulationDetailOut:
    obj = db.get(ClientPositionRegulation, regulation_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_regulation_not_found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _load_detail(db, regulation_id)


@router.delete("/{regulation_id}", status_code=204)
def delete_client_regulation(regulation_id: str, db: Session = Depends(get_db)) -> Response:
    obj = db.get(ClientPositionRegulation, regulation_id)
    if not obj:
        raise HTTPException(status_code=404, detail="client_regulation_not_found")
    for rk in db.scalars(
        select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == regulation_id)
    ).all():
        db.delete(rk)
    for ri in db.scalars(
        select(ClientRegulationInstruction).where(
            ClientRegulationInstruction.client_regulation_id == regulation_id
        )
    ).all():
        db.delete(ri)
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
