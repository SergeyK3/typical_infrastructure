# route: /api/template-org-units | file: app/routers/template_org_units.py
r"""CRUD для глобальной типовой оргструктуры (таблица template_org_units)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import TemplateOrgUnitRow
from app.schemas import ListEnvelope, TemplateOrgUnitCreate, TemplateOrgUnitOut, TemplateOrgUnitPatch
from app.utils import new_id32

router = APIRouter(prefix="/template-org-units", tags=["template_org_units"])


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
        items=[TemplateOrgUnitOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


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
        name=body.name,
        parent_code=body.parent_code,
        unit_type=body.unit_type,
        sort_order=body.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TemplateOrgUnitOut.model_validate(row)


@router.patch("/{row_id}", response_model=TemplateOrgUnitOut)
def patch_template_org_unit(
    row_id: str, body: TemplateOrgUnitPatch, db: Session = Depends(get_db)
) -> TemplateOrgUnitOut:
    row = db.get(TemplateOrgUnitRow, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="template_org_unit_not_found")
    data = body.model_dump(exclude_unset=True)
    new_parent = data.get("parent_code", row.parent_code)
    if "parent_code" in data:
        _ensure_parent_exists(db, row.template_code, new_parent)
    if new_parent == row.code:
        raise HTTPException(status_code=400, detail="template_org_parent_self")
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return TemplateOrgUnitOut.model_validate(row)


@router.delete("/{row_id}", status_code=204)
def delete_template_org_unit(row_id: str, db: Session = Depends(get_db)) -> Response:
    row = db.get(TemplateOrgUnitRow, row_id)
    if not row:
        raise HTTPException(status_code=404, detail="template_org_unit_not_found")
    children = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == row.template_code,
            TemplateOrgUnitRow.parent_code == row.code,
        )
    )
    if children:
        raise HTTPException(status_code=409, detail="template_org_unit_has_children")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
