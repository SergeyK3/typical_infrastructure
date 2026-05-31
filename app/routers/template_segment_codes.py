# route: /api/template-segment-codes | file: app/routers/template_segment_codes.py
r"""Словарь значений segment_code для шаблонов предприятия."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TemplateSegmentCode
from app.schemas import (
    ListEnvelope,
    TemplateSegmentCodeCreate,
    TemplateSegmentCodeOut,
    TemplateSegmentCodePatch,
)

router = APIRouter(prefix="/template-segment-codes", tags=["template_segment_codes"])


@router.get("", response_model=ListEnvelope[TemplateSegmentCodeOut])
def list_template_segment_codes(
    template_code: str = Query(..., min_length=1, max_length=64),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[TemplateSegmentCodeOut]:
    q = select(TemplateSegmentCode).where(TemplateSegmentCode.template_code == template_code)
    if not include_inactive:
        q = q.where(TemplateSegmentCode.is_active == True)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(TemplateSegmentCode.sort_order.asc(), TemplateSegmentCode.code.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ListEnvelope[TemplateSegmentCodeOut](
        items=[TemplateSegmentCodeOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TemplateSegmentCodeOut, status_code=201)
def create_template_segment_code(
    body: TemplateSegmentCodeCreate, db: Session = Depends(get_db)
) -> TemplateSegmentCodeOut:
    code = body.code.strip().upper()
    dup = db.get(TemplateSegmentCode, (body.template_code, code))
    if dup:
        raise HTTPException(status_code=409, detail="template_segment_code_exists")
    row = TemplateSegmentCode(
        template_code=body.template_code,
        code=code,
        label_ru=body.label_ru.strip(),
        label_en=(body.label_en or "").strip() or None,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TemplateSegmentCodeOut.model_validate(row)


@router.patch("/{template_code}/{code}", response_model=TemplateSegmentCodeOut)
def patch_template_segment_code(
    template_code: str,
    code: str,
    body: TemplateSegmentCodePatch,
    db: Session = Depends(get_db),
) -> TemplateSegmentCodeOut:
    row = db.get(TemplateSegmentCode, (template_code, code))
    if not row:
        raise HTTPException(status_code=404, detail="template_segment_code_not_found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return TemplateSegmentCodeOut.model_validate(row)


@router.delete("/{template_code}/{code}", status_code=204)
def delete_template_segment_code(
    template_code: str, code: str, db: Session = Depends(get_db)
) -> Response:
    row = db.get(TemplateSegmentCode, (template_code, code))
    if not row:
        raise HTTPException(status_code=404, detail="template_segment_code_not_found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
