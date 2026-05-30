# route: /api/positions | file: app/routers/positions.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import Client, OrgUnit, Position, PositionCatalog
from app.template_bundle_clone import resolve_client_template_code
from app.template_constants import DEFAULT_TEMPLATE_CODE
from app.position_catalog_ops import _unique_code
from app.schemas import (
    ListEnvelope,
    PositionCloneIn,
    PositionCreate,
    PositionFromCatalog,
    PositionOut,
    PositionPatch,
)
from app.utils import new_id32

router = APIRouter(prefix="/positions", tags=["positions"])


def _assert_org_unit(db: Session, client_id: str, org_unit_id: str) -> None:
    ou = db.get(OrgUnit, org_unit_id)
    if not ou or ou.client_id != client_id:
        raise HTTPException(status_code=400, detail="org_unit_not_found")


@router.get("", response_model=ListEnvelope[PositionOut])
def list_positions(
    client_id: str = Query(...),
    org_unit_id: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[PositionOut]:
    q = select(Position).where(Position.client_id == client_id)
    if org_unit_id:
        q = q.where(Position.org_unit_id == org_unit_id)
    if is_active is not None:
        q = q.where(Position.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Position.created_at.desc()).limit(limit).offset(offset)).all()
    return ListEnvelope[PositionOut](
        items=[PositionOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/export/excel")
def export_positions_excel(
    client_id: str = Query(...),
    org_unit_id: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    q = select(Position).where(Position.client_id == client_id)
    if org_unit_id:
        q = q.where(Position.org_unit_id == org_unit_id)
    if is_active is not None:
        q = q.where(Position.is_active == is_active)
    rows = db.scalars(q.order_by(Position.created_at.desc()).limit(5000)).all()
    headers = [
        "id",
        "client_id",
        "org_unit_id",
        "code",
        "name",
        "grade",
        "is_active",
        "position_catalog_code",
        "function_code",
        "position_level",
        "is_managerial",
        "is_detached",
        "created_at",
        "updated_at",
    ]
    data = [
        [
            r.id,
            r.client_id,
            r.org_unit_id,
            r.code,
            r.name,
            r.grade,
            r.is_active,
            r.position_catalog_code,
            r.function_code,
            r.position_level,
            r.is_managerial,
            r.is_detached,
            r.created_at,
            r.updated_at,
        ]
        for r in rows
    ]
    return xlsx_file_response(
        download_name=f"positions_{client_id}.xlsx",
        sheet_title="positions",
        headers=headers,
        rows=data,
    )


@router.post("/from-catalog", response_model=PositionOut, status_code=201)
def create_position_from_catalog(
    body: PositionFromCatalog, db: Session = Depends(get_db)
) -> PositionOut:
    """Создать штатную должность по записи глобального справочника position_catalog."""
    _assert_org_unit(db, body.client_id, body.org_unit_id)
    tpl_code = resolve_client_template_code(db, body.client_id)
    cat = db.get(PositionCatalog, (tpl_code, body.position_catalog_code))
    if not cat or not cat.is_active:
        raise HTTPException(status_code=404, detail="position_catalog_not_found")
    code = (body.code or cat.position_code).strip()
    name = (body.name or cat.position_name_ru).strip()
    obj = Position(
        id=new_id32(),
        client_id=body.client_id,
        org_unit_id=body.org_unit_id,
        code=code,
        name=name,
        grade=None,
        is_active=True,
        position_catalog_code=cat.position_code,
        function_code=cat.function_code,
        position_level=cat.position_level,
        is_managerial=cat.is_managerial,
        is_detached=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return PositionOut.model_validate(obj)


@router.get("/{position_id}", response_model=PositionOut)
def get_position(position_id: str, db: Session = Depends(get_db)) -> PositionOut:
    obj = db.get(Position, position_id)
    if not obj:
        raise HTTPException(status_code=404, detail="position_not_found")
    return PositionOut.model_validate(obj)


@router.post("", response_model=PositionOut)
def create_position(payload: PositionCreate, db: Session = Depends(get_db)) -> PositionOut:
    _assert_org_unit(db, payload.client_id, payload.org_unit_id)
    obj = Position(
        id=payload.id or new_id32(),
        client_id=payload.client_id,
        org_unit_id=payload.org_unit_id,
        code=payload.code,
        name=payload.name,
        grade=payload.grade,
        is_active=payload.is_active,
        position_catalog_code=payload.position_catalog_code,
        function_code=payload.function_code,
        position_level=payload.position_level,
        is_managerial=payload.is_managerial,
        is_detached=payload.is_detached,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return PositionOut.model_validate(obj)


@router.post("/{position_id}/clone", response_model=PositionOut, status_code=201)
def clone_position(
    position_id: str,
    body: PositionCloneIn,
    db: Session = Depends(get_db),
) -> PositionOut:
    source = db.get(Position, position_id)
    if not source:
        raise HTTPException(status_code=404, detail="position_not_found")

    org_unit_id = body.target_org_unit_id if body.target_org_unit_id is not None else source.org_unit_id
    _assert_org_unit(db, source.client_id, org_unit_id)

    existing_codes = set(
        db.scalars(
            select(Position.code).where(
                Position.client_id == source.client_id,
                Position.org_unit_id == org_unit_id,
            )
        ).all()
    )
    code = (body.new_code or _unique_code(existing_codes, source.code)).strip()
    if not code:
        raise HTTPException(status_code=422, detail="validation_error")
    if code in existing_codes:
        raise HTTPException(status_code=409, detail="position_code_already_exists")

    copy_name = source.name if body.name_suffix in source.name else f"{source.name} ({body.name_suffix})"
    obj = Position(
        id=new_id32(),
        client_id=source.client_id,
        org_unit_id=org_unit_id,
        code=code,
        name=copy_name,
        grade=source.grade,
        is_active=source.is_active,
        position_catalog_code=source.position_catalog_code,
        function_code=source.function_code,
        position_level=source.position_level,
        is_managerial=source.is_managerial,
        is_detached=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return PositionOut.model_validate(obj)


@router.patch("/{position_id}", response_model=PositionOut)
def patch_position(position_id: str, payload: PositionPatch, db: Session = Depends(get_db)) -> PositionOut:
    obj = db.get(Position, position_id)
    if not obj:
        raise HTTPException(status_code=404, detail="position_not_found")
    data = payload.model_dump(exclude_unset=True)
    if "org_unit_id" in data and data["org_unit_id"] is not None:
        _assert_org_unit(db, obj.client_id, data["org_unit_id"])
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return PositionOut.model_validate(obj)


@router.delete("/{position_id}", status_code=204)
def delete_position(position_id: str, db: Session = Depends(get_db)) -> Response:
    obj = db.get(Position, position_id)
    if not obj:
        raise HTTPException(status_code=404, detail="position_not_found")
    from app.models import Employee
    emp = db.scalar(select(Employee).where(Employee.position_id == position_id))
    if emp:
        raise HTTPException(status_code=400, detail="position_has_employees")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


@router.post("/bulk", response_model=list[PositionOut])
def bulk_upsert_positions(items: list[PositionCreate], db: Session = Depends(get_db)) -> list[PositionOut]:
    out: list[PositionOut] = []
    for it in items:
        obj = db.get(Position, it.id) if it.id else None
        _assert_org_unit(db, it.client_id, it.org_unit_id)
        if obj:
            if obj.client_id != it.client_id:
                raise HTTPException(status_code=400, detail="client_mismatch")
            obj.org_unit_id = it.org_unit_id
            obj.code = it.code
            obj.name = it.name
            obj.grade = it.grade
            obj.is_active = it.is_active
            obj.position_catalog_code = it.position_catalog_code
            obj.function_code = it.function_code
            obj.position_level = it.position_level
            obj.is_managerial = it.is_managerial
            obj.is_detached = it.is_detached
        else:
            obj = Position(
                id=it.id or new_id32(),
                client_id=it.client_id,
                org_unit_id=it.org_unit_id,
                code=it.code,
                name=it.name,
                grade=it.grade,
                is_active=it.is_active,
                position_catalog_code=it.position_catalog_code,
                function_code=it.function_code,
                position_level=it.position_level,
                is_managerial=it.is_managerial,
                is_detached=it.is_detached,
            )
            db.add(obj)
        db.flush()
        out.append(PositionOut.model_validate(obj))
    db.commit()
    return out

