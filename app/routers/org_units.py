# route: /api/org-units | file: app/routers/org_units.py

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.excel_export import xlsx_file_response
from app.models import Client, Employee, EnterpriseTemplate, OrgUnit
from app.client_template_apply import apply_template_to_client
from app.org_unit_ops import (
    assert_valid_unit_type,
    clone_local_department,
    clone_local_section,
    delete_local_org_unit_cascade,
    delete_local_org_unit_leaf,
    format_org_unit_name,
    normalize_template_segment_code,
    resolve_org_unit_effective_segment,
    SEGMENT_UNIT_TYPES,
)
from app.client_org_segment_sync import sync_segments_from_template
from app.template_org_resolve import resolve_template_structure
from app.schemas import (
    ListEnvelope,
    OrgUnitBulkCloneIn,
    OrgUnitCloneIn,
    OrgUnitCloneOut,
    OrgUnitCreate,
    OrgUnitFromTemplateNode,
    OrgUnitNode,
    OrgUnitOut,
    OrgUnitPatch,
    OrgUnitReorderItem,
    SegmentSyncOut,
)
from app.utils import new_id32

router = APIRouter(prefix="/org-units", tags=["org_units"])


def _org_unit_out(db: Session, row: OrgUnit) -> OrgUnitOut:
    base = OrgUnitOut.model_validate(row)
    return base.model_copy(
        update={"effective_segment_code": resolve_org_unit_effective_segment(db, row)}
    )


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


def _resolve_client_template_code(db: Session, client_id: str) -> str:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="client_not_found")
    if client.template_id:
        tpl = db.get(EnterpriseTemplate, client.template_id)
        if tpl and tpl.is_active:
            return tpl.code
    return "default"


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
        items=[_org_unit_out(db, r) for r in rows],
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
        base = _org_unit_out(db, r)
        nodes[r.id] = OrgUnitNode.model_validate(base).model_copy(update={"children": []})

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
        "segment_code",
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
            r.segment_code,
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
        name=format_org_unit_name(spec["name"], spec["unit_type"]),
        parent_id=parent_id,
        unit_type=spec["unit_type"],
        is_active=True,
        sort_order=int(spec.get("sort_order", 0)),
        catalog_source_code=spec["code"],
        is_detached=True,
        segment_code=spec.get("segment_code") if spec["unit_type"] == "department" else None,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _org_unit_out(db, obj)


@router.post("/sync-segments-from-template", response_model=SegmentSyncOut)
def sync_org_segments_from_template(
    client_id: str = Query(...),
    update_positions: bool = Query(True, description="Обновить segment_code у должностей"),
    db: Session = Depends(get_db),
) -> SegmentSyncOut:
    """Перенести segment_code из типовой оргструктуры в локальные подразделения и должности."""
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    template_code = _resolve_client_template_code(db, client_id)
    result = sync_segments_from_template(
        db, client_id, template_code, update_positions=update_positions
    )
    db.commit()
    return SegmentSyncOut(
        org_units_updated=result.org_units_updated,
        positions_updated=result.positions_updated,
    )


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
    template_code = _resolve_client_template_code(db, client_id)
    apply_template_to_client(
        db,
        client_id,
        template_code,
        include_org_units=True,
        include_positions=include_positions,
        include_regulations=include_regulations,
        update_client_template=False,
    )
    db.commit()
    rows = db.scalars(
        select(OrgUnit).where(OrgUnit.client_id == client_id).order_by(OrgUnit.sort_order.asc(), OrgUnit.created_at.asc())
    ).all()
    return [_org_unit_out(db, r) for r in rows]


@router.post("", response_model=OrgUnitOut)
def create_org_unit(payload: OrgUnitCreate, db: Session = Depends(get_db)) -> OrgUnitOut:
    assert_valid_unit_type(payload.unit_type)
    _assert_parent_ok(db, payload.client_id, payload.id, payload.parent_id)
    segment_code = normalize_template_segment_code(payload.unit_type, payload.segment_code)
    dup = db.scalar(
        select(OrgUnit).where(OrgUnit.client_id == payload.client_id, OrgUnit.code == payload.code)
    )
    if dup:
        raise HTTPException(status_code=409, detail={"code": "org_unit_code_exists", "message": "Код подразделения уже существует."})
    obj = OrgUnit(
        id=payload.id or new_id32(),
        client_id=payload.client_id,
        code=payload.code,
        name=format_org_unit_name(payload.name, payload.unit_type),
        parent_id=payload.parent_id,
        unit_type=payload.unit_type,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        catalog_source_code=payload.catalog_source_code,
        is_detached=payload.is_detached,
        segment_code=segment_code,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _org_unit_out(db, obj)


@router.patch("/{unit_id}", response_model=OrgUnitOut)
def patch_org_unit(unit_id: str, payload: OrgUnitPatch, db: Session = Depends(get_db)) -> OrgUnitOut:
    obj = _get_unit(db, unit_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data:
        _assert_parent_ok(db, obj.client_id, unit_id, data["parent_id"])
    unit_type = data.get("unit_type", obj.unit_type)
    if "segment_code" in data:
        data["segment_code"] = normalize_template_segment_code(unit_type, data["segment_code"])
    elif "unit_type" in data and unit_type not in SEGMENT_UNIT_TYPES:
        data["segment_code"] = None
    if "name" in data or "unit_type" in data:
        data["name"] = format_org_unit_name(data.get("name", obj.name), unit_type)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return _org_unit_out(db, obj)


@router.post("/{unit_id}/clone", response_model=OrgUnitCloneOut, status_code=201)
def clone_org_unit(
    unit_id: str, body: OrgUnitCloneIn, db: Session = Depends(get_db)
) -> OrgUnitCloneOut:
    obj = _get_unit(db, unit_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    if obj.unit_type == "department":
        result = clone_local_department(
            db,
            obj,
            name_suffix=body.name_suffix,
            new_code=body.new_code,
            target_parent_id=body.target_parent_id,
        )
    elif obj.unit_type == "section":
        result = clone_local_section(
            db,
            obj,
            name_suffix=body.name_suffix,
            new_code=body.new_code,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail={"code": "clone_not_supported", "message": "Копировать можно только отделение или секцию."},
        )
    db.commit()
    db.refresh(result.org_unit)
    return OrgUnitCloneOut(
        org_unit=_org_unit_out(db, result.org_unit),
        positions_created=result.positions_created,
        sections_skipped=result.sections_skipped,
    )


@router.post("/bulk-clone", response_model=list[OrgUnitCloneOut], status_code=201)
def bulk_clone_org_units(body: OrgUnitBulkCloneIn, db: Session = Depends(get_db)) -> list[OrgUnitCloneOut]:
    out: list[OrgUnitCloneOut] = []
    results = []
    for uid in body.unit_ids:
        obj = _get_unit(db, uid)
        if not obj:
            raise HTTPException(status_code=404, detail=f"org_unit_not_found:{uid}")
        if obj.unit_type != "department":
            continue
        result = clone_local_department(db, obj, name_suffix=body.name_suffix)
        results.append(result)
    db.commit()
    for result in results:
        db.refresh(result.org_unit)
        out.append(
            OrgUnitCloneOut(
                org_unit=_org_unit_out(db, result.org_unit),
                positions_created=result.positions_created,
                sections_skipped=result.sections_skipped,
            )
        )
    return out


@router.post("/reorder", response_model=list[OrgUnitOut])
def reorder_org_units(
    client_id: str = Query(...),
    body: list[OrgUnitReorderItem] = Body(...),
    db: Session = Depends(get_db),
) -> list[OrgUnitOut]:
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="client_not_found")
    out: list[OrgUnitOut] = []
    for it in body:
        obj = _get_unit(db, it.id)
        if not obj or obj.client_id != client_id:
            raise HTTPException(status_code=404, detail="org_unit_not_found")
        _assert_parent_ok(db, client_id, it.id, it.parent_id)
        obj.parent_id = it.parent_id
        obj.sort_order = it.sort_order
        out.append(_org_unit_out(db, obj))
    db.commit()
    return out


@router.delete("/{unit_id}", status_code=204)
def delete_org_unit(
    unit_id: str,
    mode: str = Query("leaf", pattern="^(leaf|cascade)$"),
    db: Session = Depends(get_db),
) -> Response:
    obj = _get_unit(db, unit_id)
    if not obj:
        raise HTTPException(status_code=404, detail="org_unit_not_found")
    if mode == "cascade":
        delete_local_org_unit_cascade(db, obj)
    else:
        delete_local_org_unit_leaf(db, obj)
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
            obj.name = format_org_unit_name(it.name, it.unit_type)
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
                name=format_org_unit_name(it.name, it.unit_type),
                parent_id=it.parent_id,
                unit_type=it.unit_type,
                is_active=it.is_active,
                sort_order=it.sort_order,
                catalog_source_code=it.catalog_source_code,
                is_detached=it.is_detached,
            )
            db.add(obj)
        db.flush()
        out.append(_org_unit_out(db, obj))
    db.commit()
    return out

