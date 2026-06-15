# route: /api/position-catalog | file: app/routers/position_catalog.py
r"""API для справочника типовых должностей (position_catalog)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import require_global_admin
from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import PositionCatalog, PositionDeptType, TemplateOrgUnitRow, TemplateSegmentCode
from app.org_unit_ops import effective_segment_from_specs
from app.position_catalog_ops import (
    clone_position_catalog,
    get_primary_dept_type_code,
    rename_position_catalog_code,
    set_primary_dept_type,
)
from app.schemas import (
    ListEnvelope,
    PositionCatalogCloneOut,
    PositionCatalogCreate,
    PositionCatalogOut,
    PositionCatalogPatch,
    PositionDeptTypeOut,
)

from app.template_constants import DEFAULT_TEMPLATE_CODE

router = APIRouter(
    prefix="/position-catalog",
    tags=["position_catalog"],
    dependencies=[Depends(require_global_admin)],
)

_SORT_COLUMNS = {
    "sort_order": PositionCatalog.sort_order,
    "position_name_ru": PositionCatalog.position_name_ru,
    "function_code": PositionCatalog.function_code,
    "position_code": PositionCatalog.position_code,
}


def _catalog_order(sort_by: str, sort_dir: str):
    col = _SORT_COLUMNS.get(sort_by, PositionCatalog.sort_order)
    primary = col.desc() if sort_dir == "desc" else col.asc()
    return primary, PositionCatalog.position_code.asc()


def _get_catalog(db: Session, template_code: str, position_code: str) -> PositionCatalog | None:
    return db.get(PositionCatalog, (template_code, position_code))


def _template_dept_segments(db: Session, template_code: str) -> dict[str, str | None]:
    rows = db.scalars(
        select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == template_code)
    ).all()
    specs = [
        {
            "code": r.code,
            "parent_code": r.parent_code,
            "unit_type": r.unit_type,
            "segment_code": r.segment_code,
        }
        for r in rows
    ]
    return {r.code: effective_segment_from_specs(specs, r.code) for r in rows if r.code}


def _segment_for_primary(
    db: Session,
    template_code: str,
    primary: str | None,
    seg_map: dict[str, str | None],
) -> str | None:
    if not primary:
        return None
    seg = seg_map.get(primary)
    if seg:
        return seg
    if db.get(TemplateSegmentCode, (template_code, primary)):
        return primary
    return None


def _catalog_out(
    db: Session,
    row: PositionCatalog,
    seg_map: dict[str, str | None] | None = None,
) -> PositionCatalogOut:
    primary = get_primary_dept_type_code(db, row.template_code, row.position_code)
    if seg_map is None:
        seg_map = _template_dept_segments(db, row.template_code)
    segment = _segment_for_primary(db, row.template_code, primary, seg_map)
    base = PositionCatalogOut.model_validate(row)
    return base.model_copy(
        update={
            "primary_dept_type_code": primary,
            "segment_code": segment,
        }
    )


@router.get("", response_model=ListEnvelope[PositionCatalogOut])
def list_position_catalog(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    function_code: str | None = Query(None, description="Фильтр по функции"),
    position_level: str | None = Query(None, description="Фильтр по уровню"),
    is_active: bool | None = Query(None, description="Фильтр по активности"),
    sort_by: str = Query("sort_order", description="Поле сортировки"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PositionCatalogOut]:
    q = select(PositionCatalog).where(PositionCatalog.template_code == template_code)
    if function_code:
        q = q.where(PositionCatalog.function_code == function_code)
    if position_level:
        q = q.where(PositionCatalog.position_level == position_level)
    if is_active is not None:
        q = q.where(PositionCatalog.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    order = _catalog_order(sort_by, sort_dir)
    rows = db.scalars(q.order_by(*order).limit(limit).offset(offset)).all()
    seg_map = _template_dept_segments(db, template_code)
    return ListEnvelope[PositionCatalogOut](
        items=[_catalog_out(db, r, seg_map) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export/excel")
def export_position_catalog_excel(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    function_code: str | None = Query(None),
    position_level: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort_by: str = Query("sort_order"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> Response:
    q = select(PositionCatalog).where(PositionCatalog.template_code == template_code)
    if function_code:
        q = q.where(PositionCatalog.function_code == function_code)
    if position_level:
        q = q.where(PositionCatalog.position_level == position_level)
    if is_active is not None:
        q = q.where(PositionCatalog.is_active == is_active)
    order = _catalog_order(sort_by, sort_dir)
    rows = db.scalars(q.order_by(*order).limit(5000)).all()
    seg_map = _template_dept_segments(db, template_code)
    headers = [
        "template_code",
        "position_code",
        "position_name_ru",
        "position_name_en",
        "function_code",
        "primary_dept_type_code",
        "segment_code",
        "position_level",
        "is_managerial",
        "position_family",
        "is_active",
        "sort_order",
        "default_regulation_code",
        "notes",
    ]
    data = []
    for r in rows:
        primary = get_primary_dept_type_code(db, r.template_code, r.position_code)
        segment = _segment_for_primary(db, r.template_code, primary, seg_map)
        data.append(
            [
                r.template_code,
                r.position_code,
                r.position_name_ru,
                r.position_name_en,
                r.function_code,
                primary,
                segment,
                r.position_level,
                r.is_managerial,
                r.position_family,
                r.is_active,
                r.sort_order,
                r.default_regulation_code,
                r.notes,
            ]
        )
    return xlsx_file_response(
        download_name=f"position_catalog_{template_code}.xlsx",
        sheet_title="position_catalog",
        headers=headers,
        rows=data,
    )


@router.post("", response_model=PositionCatalogOut, status_code=201)
def create_position_catalog(
    body: PositionCatalogCreate, db: Session = Depends(get_db)
) -> PositionCatalogOut:
    tpl = body.template_code or DEFAULT_TEMPLATE_CODE
    if _get_catalog(db, tpl, body.position_code):
        raise HTTPException(status_code=409, detail="position_code_exists")
    data = body.model_dump(exclude={"primary_dept_type_code"})
    obj = PositionCatalog(**data)
    db.add(obj)
    db.flush()
    if body.primary_dept_type_code:
        set_primary_dept_type(db, tpl, obj.position_code, body.primary_dept_type_code)
    db.commit()
    db.refresh(obj)
    return _catalog_out(db, obj)


@router.get("/{position_code}", response_model=PositionCatalogOut)
def get_position_catalog(
    position_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> PositionCatalogOut:
    obj = _get_catalog(db, template_code, position_code)
    if not obj:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    return _catalog_out(db, obj)


@router.post("/{position_code}/clone", response_model=PositionCatalogCloneOut, status_code=201)
def clone_position_catalog_row(
    position_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> PositionCatalogCloneOut:
    obj = _get_catalog(db, template_code, position_code)
    if not obj:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    result = clone_position_catalog(db, obj)
    db.commit()
    db.refresh(result.row)
    return PositionCatalogCloneOut(
        row=_catalog_out(db, result.row),
        dept_links_created=result.dept_links_created,
        regulations_created=result.regulations_created,
        kpi_templates_created=result.kpi_templates_created,
        competency_matrix_rows_created=result.competency_matrix_rows_created,
    )


@router.patch("/{position_code}", response_model=PositionCatalogOut)
def patch_position_catalog(
    position_code: str,
    body: PositionCatalogPatch,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> PositionCatalogOut:
    obj = _get_catalog(db, template_code, position_code)
    if not obj:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    data = body.model_dump(exclude_unset=True)
    new_code = data.pop("position_code", None)
    primary_dept = data.pop("primary_dept_type_code", None)
    if new_code is not None and new_code.strip() != obj.position_code:
        obj = rename_position_catalog_code(db, obj, new_code)
    for k, v in data.items():
        setattr(obj, k, v)
    if primary_dept is not None:
        set_primary_dept_type(db, obj.template_code, obj.position_code, primary_dept)
    db.commit()
    db.refresh(obj)
    return _catalog_out(db, obj)


@router.delete("/{position_code}", status_code=204)
def delete_position_catalog(
    position_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> Response:
    obj = _get_catalog(db, template_code, position_code)
    if not obj:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


@router.get("/{position_code}/dept-types", response_model=list[PositionDeptTypeOut])
def list_position_dept_types(
    position_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> list[PositionDeptTypeOut]:
    rows = db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == template_code,
            PositionDeptType.position_code == position_code,
        )
    ).all()
    return [PositionDeptTypeOut.model_validate(r) for r in rows]
