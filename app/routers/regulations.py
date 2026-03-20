# route: /api/regulations | file: app/routers/regulations.py
r"""API для справочника регламентов должностей."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import (
    KpiTemplate,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)
from app.schemas import (
    ListEnvelope,
    PositionRegulationCreate,
    PositionRegulationDetailOut,
    PositionRegulationOut,
    PositionRegulationPatch,
    RegulationInstructionOut,
    RegulationKpiOut,
)

router = APIRouter(prefix="/regulations", tags=["regulations"])


def _id(prefix: str, code: str) -> str:
    return uuid5(NAMESPACE_URL, f"seed:{prefix}:{code}").hex


def _ilike_any_regulation_column(raw: str):
    """Подстроковый поиск по основным полям (без %/_ как масок — экранируем)."""
    frag = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pat = f"%{frag}%"
    return or_(
        PositionRegulation.regulation_code.ilike(pat, escape="\\"),
        PositionRegulation.regulation_name.ilike(pat, escape="\\"),
        PositionRegulation.position_code.ilike(pat, escape="\\"),
        PositionRegulation.dept_type_code.ilike(pat, escape="\\"),
        func.coalesce(PositionRegulation.goal_summary, "").ilike(pat, escape="\\"),
        func.coalesce(PositionRegulation.notes, "").ilike(pat, escape="\\"),
    )


@router.get("", response_model=ListEnvelope[PositionRegulationOut])
def list_regulations(
    position_code: str | None = Query(None, description="Фильтр по должности"),
    dept_type_code: str | None = Query(None, description="Фильтр по типу подразделения"),
    status: str | None = Query(None, description="Фильтр по статусу"),
    is_current: bool | None = Query(None, description="Только действующие"),
    search: str | None = Query(
        None,
        max_length=200,
        description="Поиск по коду, названию, должности, типу подразделения, цели, заметкам (общесистемный реестр)",
    ),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PositionRegulationOut]:
    filters: list = []
    if position_code:
        filters.append(PositionRegulation.position_code == position_code)
    if dept_type_code:
        filters.append(PositionRegulation.dept_type_code == dept_type_code)
    if status:
        filters.append(PositionRegulation.status == status)
    if is_current is not None:
        filters.append(PositionRegulation.is_current == is_current)
    if search and (s := search.strip()):
        filters.append(_ilike_any_regulation_column(s))

    q = select(PositionRegulation)
    count_q = select(func.count()).select_from(PositionRegulation)
    for f in filters:
        q = q.where(f)
        count_q = count_q.where(f)

    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(PositionRegulation.position_code, PositionRegulation.dept_type_code, PositionRegulation.version_no)
        .limit(limit)
        .offset(offset)
    ).all()
    return ListEnvelope[PositionRegulationOut](
        items=[PositionRegulationOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# Статические маршруты — до {regulation_code}, иначе "kpi-templates" и "positions" матчатся как regulation_code
@router.get("/kpi-templates/list", response_model=list[dict])
def list_kpi_templates(db: Session = Depends(get_db)) -> list[dict]:
    """Список KPI-шаблонов для выбора при создании регламента."""
    rows = db.scalars(select(KpiTemplate).where(KpiTemplate.is_active == True)).all()
    out: list[dict] = []
    for r in rows:
        dept = None
        pos_name = None
        if r.position_code:
            dept = db.scalar(
                select(PositionDeptType.dept_type_code).where(
                    PositionDeptType.position_code == r.position_code,
                    PositionDeptType.is_primary == True,
                ).limit(1)
            )
            pc = db.get(PositionCatalog, r.position_code)
            if pc:
                pos_name = pc.position_name_ru
        out.append(
            {
                "kpi_code": r.kpi_code,
                "kpi_name": r.kpi_name,
                "unit": r.unit,
                "period_type": r.period_type,
                "default_target": r.default_target,
                "position_code": r.position_code,
                "primary_dept_type_code": dept,
                "position_name_ru": pos_name,
            }
        )
    return out


@router.get("/positions/list", response_model=list[dict])
def list_positions_for_regulation(db: Session = Depends(get_db)) -> list[dict]:
    """Список должностей из справочника для выбора при создании регламента."""
    rows = db.scalars(
        select(PositionCatalog).where(PositionCatalog.is_active == True).order_by(PositionCatalog.position_code)
    ).all()
    out: list[dict] = []
    for r in rows:
        dept = db.scalar(
            select(PositionDeptType.dept_type_code).where(
                PositionDeptType.position_code == r.position_code,
                PositionDeptType.is_primary == True,
            ).limit(1)
        )
        out.append(
            {
                "position_code": r.position_code,
                "position_name_ru": r.position_name_ru,
                "function_code": r.function_code,
                "primary_dept_type_code": dept,
            }
        )
    return out


@router.get("/export/excel")
def export_regulations_excel(
    position_code: str | None = Query(None),
    dept_type_code: str | None = Query(None),
    status: str | None = Query(None),
    is_current: bool | None = Query(None),
    search: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
) -> Response:
    filters: list = []
    if position_code:
        filters.append(PositionRegulation.position_code == position_code)
    if dept_type_code:
        filters.append(PositionRegulation.dept_type_code == dept_type_code)
    if status:
        filters.append(PositionRegulation.status == status)
    if is_current is not None:
        filters.append(PositionRegulation.is_current == is_current)
    if search and (s := search.strip()):
        filters.append(_ilike_any_regulation_column(s))
    q = select(PositionRegulation)
    for f in filters:
        q = q.where(f)
    rows = db.scalars(
        q.order_by(
            PositionRegulation.position_code,
            PositionRegulation.dept_type_code,
            PositionRegulation.version_no,
        ).limit(5000)
    ).all()
    headers = [
        "regulation_code",
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
        "id",
        "created_at",
        "updated_at",
    ]
    data = []
    for r in rows:
        o = PositionRegulationOut.model_validate(r)
        data.append(
            [
                o.regulation_code,
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
                o.id,
                o.created_at,
                o.updated_at,
            ]
        )
    return xlsx_file_response(
        download_name="regulations_global.xlsx",
        sheet_title="regulations",
        headers=headers,
        rows=data,
    )


@router.get("/{regulation_code}", response_model=PositionRegulationDetailOut)
def get_regulation(regulation_code: str, db: Session = Depends(get_db)) -> PositionRegulationDetailOut:
    q = select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code)
    obj = db.scalar(q)
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    kpis = db.scalars(select(RegulationKpi).where(RegulationKpi.regulation_code == regulation_code)).all()
    instructions = db.scalars(
        select(RegulationInstruction)
        .where(RegulationInstruction.regulation_code == regulation_code)
        .order_by(RegulationInstruction.sort_order)
    ).all()
    return PositionRegulationDetailOut(
        **PositionRegulationOut.model_validate(obj).model_dump(),
        kpis=[RegulationKpiOut.model_validate(k) for k in kpis],
        instructions=[RegulationInstructionOut.model_validate(i) for i in instructions],
    )


@router.post("", response_model=PositionRegulationOut, status_code=201)
def create_regulation(body: PositionRegulationCreate, db: Session = Depends(get_db)) -> PositionRegulationOut:
    existing = db.scalar(
        select(PositionRegulation).where(PositionRegulation.regulation_code == body.regulation_code)
    )
    if existing:
        raise HTTPException(status_code=409, detail="regulation_code_already_exists")
    obj = PositionRegulation(
        id=body.id or _id("regulation", body.regulation_code),
        regulation_code=body.regulation_code,
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
    db.commit()
    db.refresh(obj)
    return PositionRegulationOut.model_validate(obj)


@router.patch("/{regulation_code}", response_model=PositionRegulationOut)
def patch_regulation(
    regulation_code: str, body: PositionRegulationPatch, db: Session = Depends(get_db)
) -> PositionRegulationOut:
    obj = db.scalar(select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code))
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return PositionRegulationOut.model_validate(obj)


@router.delete("/{regulation_code}", status_code=204)
def delete_regulation(regulation_code: str, db: Session = Depends(get_db)) -> Response:
    obj = db.scalar(select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code))
    if not obj:
        raise HTTPException(status_code=404, detail="regulation_not_found")
    for rk in db.scalars(select(RegulationKpi).where(RegulationKpi.regulation_code == regulation_code)).all():
        db.delete(rk)
    for ri in db.scalars(select(RegulationInstruction).where(RegulationInstruction.regulation_code == regulation_code)).all():
        db.delete(ri)
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
