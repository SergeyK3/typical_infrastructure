# route: /api/kpi-templates | file: app/routers/kpi_templates.py
r"""CRUD глобальных шаблонов KPI (kpi_templates)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import KpiTemplate, PositionCatalog, PositionDeptType
from app.schemas import KpiTemplateCreate, KpiTemplateOut, KpiTemplatePatch, ListEnvelope

from app.catalog_copy_ops import clone_kpi_template
from app.template_constants import DEFAULT_TEMPLATE_CODE

router = APIRouter(prefix="/kpi-templates", tags=["kpi_templates"])


def _get_kpi(db: Session, template_code: str, kpi_code: str) -> KpiTemplate | None:
    return db.get(KpiTemplate, (template_code, kpi_code))


def _search_clause(raw: str):
    frag = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pat = f"%{frag}%"
    return or_(
        KpiTemplate.kpi_code.ilike(pat, escape="\\"),
        KpiTemplate.kpi_name.ilike(pat, escape="\\"),
        func.coalesce(KpiTemplate.formula_or_rule, "").ilike(pat, escape="\\"),
    )


def _enrich_template_out(db: Session, row: KpiTemplate) -> KpiTemplateOut:
    dept = None
    name_ru = None
    if row.position_code:
        dept = db.scalar(
            select(PositionDeptType.dept_type_code).where(
                PositionDeptType.template_code == row.template_code,
                PositionDeptType.position_code == row.position_code,
                PositionDeptType.is_primary == True,
            ).limit(1)
        )
        pc = db.get(PositionCatalog, (row.template_code, row.position_code))
        if pc:
            name_ru = pc.position_name_ru
    base = KpiTemplateOut.model_validate(row)
    return base.model_copy(
        update={
            "primary_dept_type_code": dept,
            "position_name_ru": name_ru,
        }
    )


def _ensure_position_catalog(db: Session, template_code: str, position_code: str | None) -> None:
    if position_code is None:
        return
    if not db.get(PositionCatalog, (template_code, position_code)):
        raise HTTPException(status_code=400, detail="position_catalog_not_found")


@router.get("/department-type-codes", response_model=list[str])
def list_department_type_codes_for_kpi_filter(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> list[str]:
    """Коды типов подразделений (отделений) для фильтра списка KPI-шаблонов."""
    from app.models import PositionRegulation

    reg_depts = db.scalars(
        select(PositionRegulation.dept_type_code)
        .where(
            PositionRegulation.template_code == template_code,
            PositionRegulation.dept_type_code.isnot(None),
            PositionRegulation.dept_type_code != "",
        )
        .distinct()
    ).all()
    if reg_depts:
        return sorted(set(reg_depts))
    rows = db.scalars(
        select(PositionDeptType.dept_type_code)
        .where(PositionDeptType.template_code == template_code)
        .distinct()
        .order_by(PositionDeptType.dept_type_code.asc())
    ).all()
    return list(rows)


@router.get("", response_model=ListEnvelope[KpiTemplateOut])
def list_kpi_templates(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=200),
    dept_type_code: str | None = Query(
        None,
        max_length=32,
        description="Фильтр: только шаблоны, привязанные к типовой должности с этим основным типом подразделения",
    ),
    position_code: str | None = Query(
        None,
        max_length=64,
        description="Фильтр: шаблоны с привязкой к указанной типовой должности (position_catalog)",
    ),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[KpiTemplateOut]:
    q = select(KpiTemplate).where(KpiTemplate.template_code == template_code)
    count_q = select(func.count()).select_from(KpiTemplate).where(KpiTemplate.template_code == template_code)
    if is_active is not None:
        q = q.where(KpiTemplate.is_active == is_active)
        count_q = count_q.where(KpiTemplate.is_active == is_active)
    if search and (s := search.strip()):
        q = q.where(_search_clause(s))
        count_q = count_q.where(_search_clause(s))
    if dept_type_code and (d := dept_type_code.strip()):
        in_dept = select(PositionDeptType.position_code).where(
            PositionDeptType.template_code == template_code,
            PositionDeptType.dept_type_code == d,
            PositionDeptType.is_primary == True,
        )
        q = q.where(KpiTemplate.position_code.in_(in_dept))
        count_q = count_q.where(KpiTemplate.position_code.in_(in_dept))
    if position_code and (pc := position_code.strip()):
        q = q.where(KpiTemplate.position_code == pc)
        count_q = count_q.where(KpiTemplate.position_code == pc)
    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(KpiTemplate.kpi_code.asc()).limit(limit).offset(offset)
    ).all()
    return ListEnvelope[KpiTemplateOut](
        items=[_enrich_template_out(db, r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export/excel")
def export_kpi_templates_excel(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=200),
    dept_type_code: str | None = Query(None, max_length=32),
    position_code: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
) -> Response:
    q = select(KpiTemplate).where(KpiTemplate.template_code == template_code)
    if is_active is not None:
        q = q.where(KpiTemplate.is_active == is_active)
    if search and (s := search.strip()):
        q = q.where(_search_clause(s))
    if dept_type_code and (d := dept_type_code.strip()):
        in_dept = select(PositionDeptType.position_code).where(
            PositionDeptType.template_code == template_code,
            PositionDeptType.dept_type_code == d,
            PositionDeptType.is_primary == True,
        )
        q = q.where(KpiTemplate.position_code.in_(in_dept))
    if position_code and (pc := position_code.strip()):
        q = q.where(KpiTemplate.position_code == pc)
    rows = db.scalars(q.order_by(KpiTemplate.kpi_code.asc()).limit(5000)).all()
    headers = [
        "kpi_code",
        "kpi_name",
        "unit",
        "period_type",
        "formula_or_rule",
        "default_target",
        "is_active",
        "position_code",
        "primary_dept_type_code",
        "position_name_ru",
    ]
    data = []
    for r in rows:
        o = _enrich_template_out(db, r)
        data.append(
            [
                o.kpi_code,
                o.kpi_name,
                o.unit,
                o.period_type,
                o.formula_or_rule,
                o.default_target,
                o.is_active,
                o.position_code,
                o.primary_dept_type_code,
                o.position_name_ru,
            ]
        )
    return xlsx_file_response(
        download_name="kpi_templates.xlsx",
        sheet_title="kpi_templates",
        headers=headers,
        rows=data,
    )


@router.get("/{kpi_code}", response_model=KpiTemplateOut)
def get_kpi_template(
    kpi_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> KpiTemplateOut:
    obj = _get_kpi(db, template_code, kpi_code)
    if not obj:
        raise HTTPException(status_code=404, detail="kpi_template_not_found")
    return _enrich_template_out(db, obj)


@router.post("", response_model=KpiTemplateOut, status_code=201)
def create_kpi_template(
    body: KpiTemplateCreate, db: Session = Depends(get_db)
) -> KpiTemplateOut:
    tpl = body.template_code or DEFAULT_TEMPLATE_CODE
    if _get_kpi(db, tpl, body.kpi_code):
        raise HTTPException(status_code=409, detail="kpi_code_exists")
    _ensure_position_catalog(db, tpl, body.position_code)
    obj = KpiTemplate(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _enrich_template_out(db, obj)


@router.post("/{kpi_code}/clone", response_model=KpiTemplateOut, status_code=201)
def clone_kpi_template_row(
    kpi_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> KpiTemplateOut:
    obj = _get_kpi(db, template_code, kpi_code)
    if not obj:
        raise HTTPException(status_code=404, detail="kpi_template_not_found")
    row = clone_kpi_template(db, obj)
    db.commit()
    db.refresh(row)
    return _enrich_template_out(db, row)


@router.patch("/{kpi_code}", response_model=KpiTemplateOut)
def patch_kpi_template(
    kpi_code: str,
    body: KpiTemplatePatch,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> KpiTemplateOut:
    obj = _get_kpi(db, template_code, kpi_code)
    if not obj:
        raise HTTPException(status_code=404, detail="kpi_template_not_found")
    data = body.model_dump(exclude_unset=True)
    if "position_code" in data:
        _ensure_position_catalog(db, template_code, data["position_code"])
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _enrich_template_out(db, obj)


@router.delete("/{kpi_code}", status_code=204)
def delete_kpi_template(
    kpi_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> Response:
    obj = _get_kpi(db, template_code, kpi_code)
    if not obj:
        raise HTTPException(status_code=404, detail="kpi_template_not_found")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)
