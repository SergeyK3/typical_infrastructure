# route: /api/org-units | file: app/routers/org_units.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import Client, Employee, OrgUnit, Position
from app.models import PositionCatalog, PositionDeptType
from app.client_catalog_sync import sync_global_regulations_to_client
from app.template_org_resolve import resolve_template_structure
from app.schemas import ListEnvelope, OrgUnitCreate, OrgUnitFromTemplateNode, OrgUnitNode, OrgUnitOut, OrgUnitPatch
from app.utils import new_id32

router = APIRouter(prefix="/org-units", tags=["org_units"])


def _get_unit(db: Session, unit_id: str) -> OrgUnit | None:
    return db.get(OrgUnit, unit_id)


def _assert_parent_ok(db: Session, client_id: str, unit_id: str | None, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if unit_id is not None and parent_id == unit_id:
        raise HTTPException(status_code=400, detail="org_unit_cycle")
    parent = _get_unit(db, parent_id)
    if not parent or parent.client_id != client_id:
        raise HTTPException(status_code=400, detail="parent_not_found")

    # Cycle protection: walk up the parent chain and ensure we don't reach unit_id.
    if unit_id is None:
        return
    seen: set[str] = set()
    cur = parent
    while cur.parent_id:
        if cur.parent_id in seen:
            # Existing broken data; treat as a cycle to be safe.
            raise HTTPException(status_code=400, detail="org_unit_cycle")
        seen.add(cur.parent_id)
        if cur.parent_id == unit_id:
            raise HTTPException(status_code=400, detail="org_unit_cycle")
        nxt = _get_unit(db, cur.parent_id)
        if not nxt:
            break
        cur = nxt


@router.get("", response_model=ListEnvelope[OrgUnitOut])
def list_org_units(
    client_id: str = Query(...),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> ListEnvelope[OrgUnitOut]:
    q = select(OrgUnit).where(OrgUnit.client_id == client_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(OrgUnit.sort_order.asc(), OrgUnit.created_at.asc()).limit(limit).offset(offset)
    ).all()
    return ListEnvelope[OrgUnitOut](
        items=[OrgUnitOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/tree", response_model=list[OrgUnitNode])
def tree_org_units(client_id: str = Query(...), db: Session = Depends(get_db)) -> list[OrgUnitNode]:
    rows = db.scalars(
        select(OrgUnit).where(OrgUnit.client_id == client_id).order_by(OrgUnit.sort_order.asc(), OrgUnit.created_at.asc())
    ).all()
    nodes: dict[str, OrgUnitNode] = {}
    for r in rows:
        nodes[r.id] = OrgUnitNode.model_validate(r).model_copy(update={"children": []})

    roots: list[OrgUnitNode] = []
    for n in nodes.values():
        if n.parent_id and n.parent_id in nodes:
            nodes[n.parent_id].children.append(n)
        else:
            roots.append(n)

    # Children order
    def sort_children(node: OrgUnitNode) -> None:
        node.children.sort(key=lambda x: (x.sort_order, x.created_at))
        for c in node.children:
            sort_children(c)

    for r in roots:
        sort_children(r)
    roots.sort(key=lambda x: (x.sort_order, x.created_at))
    return roots


@router.get("/export/excel")
def export_org_units_excel(
    client_id: str = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    q = select(OrgUnit).where(OrgUnit.client_id == client_id)
    rows = db.scalars(
        q.order_by(OrgUnit.sort_order.asc(), OrgUnit.created_at.asc()).limit(5000)
    ).all()
    headers = [
        "id",
        "client_id",
        "code",
        "name",
        "parent_id",
        "unit_type",
        "is_active",
        "sort_order",
        "catalog_source_code",
        "is_detached",
        "created_at",
        "updated_at",
    ]
    data = [
        [
            r.id,
            r.client_id,
            r.code,
            r.name,
            r.parent_id,
            r.unit_type,
            r.is_active,
            r.sort_order,
            r.catalog_source_code,
            r.is_detached,
            r.created_at,
            r.updated_at,
        ]
        for r in rows
    ]
    return xlsx_file_response(
        download_name=f"org_units_{client_id}.xlsx",
        sheet_title="org_units",
        headers=headers,
        rows=data,
    )


@router.post("/from-template-node", response_model=OrgUnitOut, status_code=201)
def add_org_unit_from_template(
    body: OrgUnitFromTemplateNode, db: Session = Depends(get_db)
) -> OrgUnitOut:
    """Создать одно подразделение по узлу типового шаблона (родитель должен уже существовать у клиента)."""
    if not db.get(Client, body.client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    structure = resolve_template_structure(db, body.template_code)
    spec = next((x for x in structure if x["code"] == body.template_unit_code), None)
    if not spec:
        raise HTTPException(status_code=404, detail="template_unit_not_found")
    exists = db.scalar(
        select(OrgUnit).where(
            OrgUnit.client_id == body.client_id,
            OrgUnit.code == spec["code"],
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="org_unit_code_exists")
    parent_id: str | None = None
    if spec.get("parent_code"):
        parent = db.scalar(
            select(OrgUnit).where(
                OrgUnit.client_id == body.client_id,
                OrgUnit.code == spec["parent_code"],
            )
        )
        if not parent:
            raise HTTPException(
                status_code=400,
                detail="template_parent_missing",
            )
        parent_id = parent.id
    obj = OrgUnit(
        id=new_id32(),
        client_id=body.client_id,
        code=spec["code"],
        name=spec["name"],
        parent_id=parent_id,
        unit_type=spec["unit_type"],
        is_active=True,
        sort_order=int(spec.get("sort_order", 0)),
        catalog_source_code=spec["code"],
        is_detached=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return OrgUnitOut.model_validate(obj)


@router.post("/deploy-template", response_model=list[OrgUnitOut])
def deploy_template(
    client_id: str = Query(...),
    include_positions: bool = Query(True, description="Развернуть типовые должности"),
    include_regulations: bool = Query(
        True,
        description="Скопировать глобальные регламенты и KPI в справочник организации (по развёрнутым должностям)",
    ),
    db: Session = Depends(get_db),
) -> list[OrgUnitOut]:
    """Развернуть типовую оргструктуру (отделения, секции и должности) для организации."""
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    structure = resolve_template_structure(db, "default")
    ids_by_code: dict[str, str] = {}
    existing = {r.code: r for r in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()}
    for spec in structure:
        if spec["code"] in existing:
            ids_by_code[spec["code"]] = existing[spec["code"]].id
            continue
        parent_id = ids_by_code.get(spec["parent_code"]) if spec.get("parent_code") else None
        obj = OrgUnit(
            id=new_id32(),
            client_id=client_id,
            code=spec["code"],
            name=spec["name"],
            parent_id=parent_id,
            unit_type=spec["unit_type"],
            is_active=True,
            sort_order=int(spec.get("sort_order", 0)),
            catalog_source_code=spec["code"],
            is_detached=True,
        )
        db.add(obj)
        db.flush()
        ids_by_code[spec["code"]] = obj.id
    if include_positions:
        catalog_by_code = {r.position_code: r for r in db.scalars(select(PositionCatalog).where(PositionCatalog.is_active)).all()}
        dept_links = db.scalars(select(PositionDeptType)).all()
        existing_pos = {(p.code, p.org_unit_id): p for p in db.scalars(select(Position).where(Position.client_id == client_id)).all()}
        for link in dept_links:
            catalog = catalog_by_code.get(link.position_code)
            if not catalog:
                continue
            ou_id = ids_by_code.get(link.dept_type_code)
            if not ou_id:
                continue
            if (catalog.position_code, ou_id) in existing_pos:
                continue
            pos = Position(
                id=new_id32(),
                client_id=client_id,
                org_unit_id=ou_id,
                code=catalog.position_code,
                name=catalog.position_name_ru,
                grade=None,
                is_active=True,
                position_catalog_code=catalog.position_code,
                function_code=catalog.function_code,
                position_level=catalog.position_level,
                is_managerial=catalog.is_managerial,
                is_detached=True,
            )
            db.add(pos)
            db.flush()
            existing_pos[(catalog.position_code, ou_id)] = pos
    if include_regulations:
        sync_global_regulations_to_client(db, client_id)
    db.commit()
    rows = db.scalars(
        select(OrgUnit).where(OrgUnit.client_id == client_id).order_by(OrgUnit.sort_order.asc(), OrgUnit.created_at.asc())
    ).all()
    return [OrgUnitOut.model_validate(r) for r in rows]


@router.post("", response_model=OrgUnitOut)
def create_org_unit(payload: OrgUnitCreate, db: Session = Depends(get_db)) -> OrgUnitOut:
    _assert_parent_ok(db, payload.client_id, payload.id, payload.parent_id)
    obj = OrgUnit(
        id=payload.id or new_id32(),
        client_id=payload.client_id,
        code=payload.code,
        name=payload.name,
        parent_id=payload.parent_id,
        unit_type=payload.unit_type,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        catalog_source_code=payload.catalog_source_code,
        is_detached=payload.is_detached,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return OrgUnitOut.model_validate(obj)


@router.patch("/{unit_id}", response_model=OrgUnitOut)
def patch_org_unit(unit_id: str, payload: OrgUnitPatch, db: Session = Depends(get_db)) -> OrgUnitOut:
    obj = _get_unit(db, unit_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        _assert_parent_ok(db, obj.client_id, unit_id, data["parent_id"])
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return OrgUnitOut.model_validate(obj)


@router.delete("/{unit_id}", status_code=204)
def delete_org_unit(unit_id: str, db: Session = Depends(get_db)) -> Response:
    obj = _get_unit(db, unit_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    children = db.scalars(select(OrgUnit).where(OrgUnit.parent_id == unit_id)).all()
    if children:
        raise HTTPException(status_code=400, detail="org_unit_has_children")
    positions = db.scalars(select(Position).where(Position.org_unit_id == unit_id)).all()
    if positions:
        raise HTTPException(status_code=400, detail="org_unit_has_positions")
    employees = db.scalars(select(Employee).where(Employee.org_unit_id == unit_id)).all()
    if employees:
        raise HTTPException(status_code=400, detail="org_unit_has_employees")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


@router.post("/bulk", response_model=list[OrgUnitOut])
def bulk_upsert_org_units(items: list[OrgUnitCreate], db: Session = Depends(get_db)) -> list[OrgUnitOut]:
    out: list[OrgUnitOut] = []
    for it in items:
        unit_id = it.id
        if unit_id:
            obj = _get_unit(db, unit_id)
        else:
            obj = None

        if obj:
            if obj.client_id != it.client_id:
                raise HTTPException(status_code=400, detail="client_mismatch")
            _assert_parent_ok(db, it.client_id, obj.id, it.parent_id)
            obj.code = it.code
            obj.name = it.name
            obj.parent_id = it.parent_id
            obj.unit_type = it.unit_type
            obj.is_active = it.is_active
            obj.sort_order = it.sort_order
            obj.is_detached = it.is_detached
        else:
            _assert_parent_ok(db, it.client_id, it.id, it.parent_id)
            obj = OrgUnit(
                id=it.id or new_id32(),
                client_id=it.client_id,
                code=it.code,
                name=it.name,
                parent_id=it.parent_id,
                unit_type=it.unit_type,
                is_active=it.is_active,
                sort_order=it.sort_order,
                catalog_source_code=it.catalog_source_code,
                is_detached=it.is_detached,
            )
            db.add(obj)
        db.flush()
        out.append(OrgUnitOut.model_validate(obj))
    db.commit()
    return out

