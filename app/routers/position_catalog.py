# route: /api/position-catalog | file: app/routers/position_catalog.py
r"""API для справочника типовых должностей (position_catalog)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import PositionCatalog, PositionDeptType
from app.schemas import (
    ListEnvelope,
    PositionCatalogCreate,
    PositionCatalogOut,
    PositionCatalogPatch,
    PositionDeptTypeOut,
)

from app.template_constants import DEFAULT_TEMPLATE_CODE

router = APIRouter(prefix="/position-catalog", tags=["position_catalog"])


def _get_catalog(db: Session, template_code: str, position_code: str) -> PositionCatalog | None:
    return db.get(PositionCatalog, (template_code, position_code))


@router.get("", response_model=ListEnvelope[PositionCatalogOut])
def list_position_catalog(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    function_code: str | None = Query(None, description="Фильтр по функции"),
    is_active: bool | None = Query(None, description="Фильтр по активности"),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PositionCatalogOut]:
    q = select(PositionCatalog).where(PositionCatalog.template_code == template_code)
    if function_code:
        q = q.where(PositionCatalog.function_code == function_code)
    if is_active is not None:
        q = q.where(PositionCatalog.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(PositionCatalog.function_code, PositionCatalog.position_code).limit(limit).offset(offset)).all()
    return ListEnvelope[PositionCatalogOut](
        items=[PositionCatalogOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export/excel")
def export_position_catalog_excel(
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    function_code: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    q = select(PositionCatalog).where(PositionCatalog.template_code == template_code)
    if function_code:
        q = q.where(PositionCatalog.function_code == function_code)
    if is_active is not None:
        q = q.where(PositionCatalog.is_active == is_active)
    rows = db.scalars(q.order_by(PositionCatalog.function_code, PositionCatalog.position_code).limit(5000)).all()
    headers = [
        "template_code",
        "position_code",
        "position_name_ru",
        "position_name_en",
        "function_code",
        "position_level",
        "is_managerial",
        "position_family",
        "is_active",
        "default_regulation_code",
        "notes",
    ]
    data = [
        [
            r.template_code,
            r.position_code,
            r.position_name_ru,
            r.position_name_en,
            r.function_code,
            r.position_level,
            r.is_managerial,
            r.position_family,
            r.is_active,
            r.default_regulation_code,
            r.notes,
        ]
        for r in rows
    ]
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
    obj = PositionCatalog(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return PositionCatalogOut.model_validate(obj)


@router.get("/{position_code}", response_model=PositionCatalogOut)
def get_position_catalog(
    position_code: str,
    template_code: str = Query(DEFAULT_TEMPLATE_CODE, min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> PositionCatalogOut:
    obj = _get_catalog(db, template_code, position_code)
    if not obj:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    return PositionCatalogOut.model_validate(obj)


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
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return PositionCatalogOut.model_validate(obj)


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
