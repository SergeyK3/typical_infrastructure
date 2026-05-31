# route: /api/template-org-units | file: app/routers/template_org_units.py
r"""CRUD для глобальной типовой оргструктуры (таблица template_org_units)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import PositionDeptType, TemplateOrgUnitRow
from app.org_unit_ops import (
    LOG_GROUP_UNIT_TYPES,
    SEGMENT_UNIT_TYPES,
    assert_not_protected_code,
    assert_valid_unit_type,
    clone_template_department,
    clone_template_section,
    delete_template_org_unit_cascade,
    delete_template_org_unit_leaf,
    normalize_template_log_group,
    normalize_template_segment_code,
    rename_template_org_unit_code,
    format_org_unit_name,
    effective_segment_from_specs,
    template_delete_impact,
)
from app.schemas import (
    ListEnvelope,
    TemplateOrgUnitCloneOut,
    TemplateOrgUnitCreate,
    TemplateOrgUnitNode,
    TemplateOrgUnitOut,
    TemplateOrgUnitPatch,
)
from app.utils import new_id32

router = APIRouter(prefix="/template-org-units", tags=["template_org_units"])


def _segment_specs(rows: list[TemplateOrgUnitRow]) -> list[dict]:
    return [
        {
            "code": r.code,
            "parent_code": r.parent_code,
            "unit_type": r.unit_type,
            "segment_code": r.segment_code,
        }
        for r in rows
    ]


def _template_org_out(row: TemplateOrgUnitRow, all_rows: list[TemplateOrgUnitRow]) -> TemplateOrgUnitOut:
    specs = _segment_specs(all_rows)
    base = TemplateOrgUnitOut.model_validate(row)
    return base.model_copy(
        update={"effective_segment_code": effective_segment_from_specs(specs, row.code)}
    )


def _ensure_parent_exists(
    db: Session, template_code: str, parent_code: str | None
) -> None:
    if not parent_code:
        return
    ok = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == template_code,
            TemplateOrgUnitRow.code == parent_code,
        )
    )
    if not ok:
        raise HTTPException(status_code=400, detail="template_parent_not_found")


def _position_counts_by_dept(db: Session, template_code: str) -> dict[str, int]:
    rows = db.execute(
        select(PositionDeptType.dept_type_code, func.count())
        .where(PositionDeptType.template_code == template_code)
        .group_by(PositionDeptType.dept_type_code)
    ).all()
    return {code: int(cnt) for code, cnt in rows}


@router.get("", response_model=ListEnvelope[TemplateOrgUnitOut])
def list_template_org_units(
    template_code: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[TemplateOrgUnitOut]:
    q = select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == template_code)
    total = db.scalar(
        select(func.count()).select_from(TemplateOrgUnitRow).where(
            TemplateOrgUnitRow.template_code == template_code
        )
    ) or 0
    rows = db.scalars(
        q.order_by(TemplateOrgUnitRow.sort_order.asc(), TemplateOrgUnitRow.code.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ListEnvelope[TemplateOrgUnitOut](
        items=[_template_org_out(r, rows) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tree", response_model=list[TemplateOrgUnitNode])
def tree_template_org_units(
    template_code: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> list[TemplateOrgUnitNode]:
    rows = db.scalars(
        select(TemplateOrgUnitRow)
        .where(TemplateOrgUnitRow.template_code == template_code)
        .order_by(TemplateOrgUnitRow.sort_order.asc(), TemplateOrgUnitRow.code.asc())
    ).all()
    pos_counts = _position_counts_by_dept(db, template_code)
    specs = _segment_specs(rows)
    by_code = {r.code: r for r in rows}
    nodes: dict[str, TemplateOrgUnitNode] = {}
    for r in rows:
        base = _template_org_out(r, rows)
        nodes[r.code] = TemplateOrgUnitNode.model_validate(base).model_copy(
            update={"children": [], "position_count": pos_counts.get(r.code, 0)}
        )

    roots: list[TemplateOrgUnitNode] = []
    for n in nodes.values():
        if n.parent_code and n.parent_code in nodes:
            nodes[n.parent_code].children.append(n)
        else:
            roots.append(n)

    def sort_children(node: TemplateOrgUnitNode) -> None:
        node.children.sort(key=lambda x: (x.sort_order, x.code))
        for c in node.children:
            sort_children(c)

    for r in roots:
        sort_children(r)
    roots.sort(key=lambda x: (x.sort_order, x.code))
    return roots


@router.get("/{row_id}/delete-impact")
def get_template_delete_impact(row_id: str, db: Session = Depends(get_db)) -> dict:
    row = db.get(TemplateOrgUnitRow, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="template_org_unit_not_found")
    return template_delete_impact(db, row)


@router.get("/export/excel")
def export_template_org_units_excel(
    template_code: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> Response:
    q = select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == template_code)
    rows = db.scalars(
        q.order_by(TemplateOrgUnitRow.sort_order.asc(), TemplateOrgUnitRow.code.asc()).limit(5000)
    ).all()
    headers = [
        "id",
        "template_code",
        "code",
        "name",
        "parent_code",
        "unit_type",
        "log_group",
        "segment_code",
        "sort_order",
        "created_at",
        "updated_at",
    ]
    data = [
        [
            r.id,
            r.template_code,
            r.code,
            r.name,
            r.parent_code,
            r.unit_type,
            r.log_group,
            r.segment_code,
            r.sort_order,
            r.created_at,
            r.updated_at,
        ]
        for r in rows
    ]
    fn = f"template_org_{template_code}.xlsx"
    return xlsx_file_response(download_name=fn, sheet_title="template_org", headers=headers, rows=data)


@router.post("", response_model=TemplateOrgUnitOut, status_code=201)
def create_template_org_unit(
    body: TemplateOrgUnitCreate, db: Session = Depends(get_db)
) -> TemplateOrgUnitOut:
    assert_valid_unit_type(body.unit_type)
    log_group = normalize_template_log_group(body.unit_type, body.log_group)
    segment_code = normalize_template_segment_code(body.unit_type, body.segment_code)
    dup = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == body.template_code,
            TemplateOrgUnitRow.code == body.code,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail="template_org_unit_code_exists")
    _ensure_parent_exists(db, body.template_code, body.parent_code)
    row = TemplateOrgUnitRow(
        id=new_id32(),
        template_code=body.template_code,
        code=body.code,
        name=format_org_unit_name(body.name, body.unit_type),
        parent_code=body.parent_code,
        unit_type=body.unit_type,
        sort_order=body.sort_order,
        log_group=log_group,
        segment_code=segment_code,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    all_rows = db.scalars(
        select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == body.template_code)
    ).all()
    return _template_org_out(row, all_rows)


@router.post("/{row_id}/clone", response_model=TemplateOrgUnitCloneOut, status_code=201)
def clone_template_org_unit(row_id: str, db: Session = Depends(get_db)) -> TemplateOrgUnitCloneOut:
    row = db.get(TemplateOrgUnitRow, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="template_org_unit_not_found")
    if row.unit_type == "department":
        result = clone_template_department(db, row)
    elif row.unit_type == "section":
        result = clone_template_section(db, row)
    else:
        raise HTTPException(
            status_code=400,
            detail={"code": "clone_not_supported", "message": "Копировать можно только отделение или секцию."},
        )
    db.commit()
    db.refresh(result.row)
    all_rows = db.scalars(
        select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == result.row.template_code)
    ).all()
    return TemplateOrgUnitCloneOut(
        row=_template_org_out(result.row, all_rows),
        position_links_created=result.position_links_created,
        sections_skipped=result.sections_skipped,
    )


@router.patch("/{row_id}", response_model=TemplateOrgUnitOut)
def patch_template_org_unit(
    row_id: str, body: TemplateOrgUnitPatch, db: Session = Depends(get_db)
) -> TemplateOrgUnitOut:
    row = db.get(TemplateOrgUnitRow, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="template_org_unit_not_found")
    data = body.model_dump(exclude_unset=True)
    if "code" in data and data["code"] is not None:
        rename_template_org_unit_code(db, row, data.pop("code"))
    if "unit_type" in data and data["unit_type"] is not None:
        assert_valid_unit_type(data["unit_type"])
    new_parent = data.get("parent_code", row.parent_code)
    if "parent_code" in data:
        _ensure_parent_exists(db, row.template_code, new_parent)
    if new_parent == row.code:
        raise HTTPException(status_code=400, detail="template_org_parent_self")
    unit_type = data.get("unit_type", row.unit_type)
    if "log_group" in data:
        data["log_group"] = normalize_template_log_group(unit_type, data["log_group"])
    elif "unit_type" in data and unit_type not in LOG_GROUP_UNIT_TYPES:
        data["log_group"] = None
    if "segment_code" in data:
        data["segment_code"] = normalize_template_segment_code(unit_type, data["segment_code"])
    elif "unit_type" in data and unit_type not in SEGMENT_UNIT_TYPES:
        data["segment_code"] = None
    if "name" in data or "unit_type" in data:
        current_name = data.get("name", row.name)
        data["name"] = format_org_unit_name(current_name, unit_type)
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    all_rows = db.scalars(
        select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == row.template_code)
    ).all()
    return _template_org_out(row, all_rows)
def delete_template_org_unit(
    row_id: str,
    mode: str = Query("leaf", pattern="^(leaf|cascade)$"),
    db: Session = Depends(get_db),
) -> Response:
    row = db.get(TemplateOrgUnitRow, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="template_org_unit_not_found")
    if mode == "cascade":
        delete_template_org_unit_cascade(db, row)
    else:
        delete_template_org_unit_leaf(db, row)
    db.commit()
    return Response(status_code=204)
