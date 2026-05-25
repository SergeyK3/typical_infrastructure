r"""Операции клонирования и каскадного удаления подразделений (локальные и глобальные)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Employee, OrgUnit, Position, PositionDeptType, TemplateOrgUnitRow
from app.utils import new_id32

PROTECTED_ORG_CODES = frozenset({"company"})
VALID_UNIT_TYPES = frozenset({"company", "department", "section"})


def assert_valid_unit_type(unit_type: str) -> None:
    if unit_type not in VALID_UNIT_TYPES:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_unit_type", "message": f"unit_type must be one of: {', '.join(sorted(VALID_UNIT_TYPES))}"},
        )


def assert_not_protected_code(code: str) -> None:
    if code in PROTECTED_ORG_CODES:
        raise HTTPException(
            status_code=403,
            detail={"code": "org_unit_protected", "message": "Системный узел нельзя удалить или клонировать."},
        )


def _local_codes(db: Session, client_id: str) -> set[str]:
    rows = db.scalars(select(OrgUnit.code).where(OrgUnit.client_id == client_id)).all()
    return set(rows)


def _unique_local_code(db: Session, client_id: str, base: str) -> str:
    existing = _local_codes(db, client_id)
    candidate = f"{base}_COPY"
    if candidate not in existing:
        return candidate
    n = 2
    while True:
        candidate = f"{base}_COPY_{n}"
        if candidate not in existing:
            return candidate
        n += 1


def _collect_subtree_ids(db: Session, root_id: str) -> list[str]:
    """Root first, then descendants (BFS)."""
    all_units = db.scalars(select(OrgUnit)).all()
    by_parent: dict[str | None, list[OrgUnit]] = {}
    by_id = {u.id: u for u in all_units}
    if root_id not in by_id:
        return []
    for u in all_units:
        by_parent.setdefault(u.parent_id, []).append(u)

    out: list[str] = [root_id]
    queue = [root_id]
    while queue:
        cur = queue.pop(0)
        for ch in by_parent.get(cur, []):
            out.append(ch.id)
            queue.append(ch.id)
    return out


def _subtree_employee_blockers(db: Session, unit_ids: list[str]) -> list[dict]:
    if not unit_ids:
        return []
    blockers: list[dict] = []
    for emp in db.scalars(select(Employee).where(Employee.org_unit_id.in_(unit_ids))).all():
        blockers.append({"employee_id": emp.id, "org_unit_id": emp.org_unit_id, "via": "org_unit_id"})
    pos_ids = [
        p.id
        for p in db.scalars(select(Position).where(Position.org_unit_id.in_(unit_ids))).all()
    ]
    if pos_ids:
        for emp in db.scalars(select(Employee).where(Employee.position_id.in_(pos_ids))).all():
            blockers.append({"employee_id": emp.id, "position_id": emp.position_id, "via": "position_id"})
    return blockers


@dataclass
class LocalCloneResult:
    org_unit: OrgUnit
    positions_created: int
    sections_skipped: int


def clone_local_department(
    db: Session,
    source: OrgUnit,
    *,
    name_suffix: str = "Копия",
    new_code: str | None = None,
    target_parent_id: str | None = None,
) -> LocalCloneResult:
    if source.unit_type != "department":
        raise HTTPException(
            status_code=400,
            detail={"code": "clone_source_not_department", "message": "Копировать можно только отделение (department)."},
        )
    assert_not_protected_code(source.code)

    parent_id = target_parent_id if target_parent_id is not None else source.parent_id
    if parent_id:
        parent = db.get(OrgUnit, parent_id)
        if not parent or parent.client_id != source.client_id:
            raise HTTPException(status_code=400, detail={"code": "parent_not_found", "message": "Родитель не найден."})

    code = (new_code or _unique_local_code(db, source.client_id, source.code)).strip()
    if not code:
        raise HTTPException(status_code=422, detail={"code": "validation_error", "message": "Код обязателен."})
    dup = db.scalar(
        select(OrgUnit).where(OrgUnit.client_id == source.client_id, OrgUnit.code == code)
    )
    if dup:
        raise HTTPException(status_code=409, detail={"code": "org_unit_code_exists", "message": "Код подразделения уже существует."})

    sections_skipped = db.scalar(
        select(func.count()).select_from(OrgUnit).where(OrgUnit.parent_id == source.id)
    ) or 0

    copy_name = source.name if name_suffix in source.name else f"{source.name} ({name_suffix})"
    new_ou = OrgUnit(
        id=new_id32(),
        client_id=source.client_id,
        code=code,
        name=copy_name,
        parent_id=parent_id,
        unit_type="department",
        is_active=source.is_active,
        sort_order=source.sort_order + 1,
        catalog_source_code=None,
        is_detached=True,
    )
    db.add(new_ou)
    db.flush()

    positions_created = 0
    for pos in db.scalars(select(Position).where(Position.org_unit_id == source.id)).all():
        new_pos = Position(
            id=new_id32(),
            client_id=pos.client_id,
            org_unit_id=new_ou.id,
            code=pos.code,
            name=pos.name,
            grade=pos.grade,
            is_active=pos.is_active,
            position_catalog_code=pos.position_catalog_code,
            function_code=pos.function_code,
            position_level=pos.position_level,
            is_managerial=pos.is_managerial,
            is_detached=True,
        )
        db.add(new_pos)
        positions_created += 1

    db.flush()
    return LocalCloneResult(org_unit=new_ou, positions_created=positions_created, sections_skipped=int(sections_skipped))


def delete_local_org_unit_leaf(db: Session, obj: OrgUnit) -> None:
    assert_not_protected_code(obj.code)
    children = db.scalars(select(OrgUnit).where(OrgUnit.parent_id == obj.id)).all()
    if children:
        raise HTTPException(status_code=400, detail={"code": "org_unit_has_children", "message": "Есть дочерние подразделения."})
    positions = db.scalars(select(Position).where(Position.org_unit_id == obj.id)).all()
    if positions:
        raise HTTPException(status_code=400, detail={"code": "org_unit_has_positions", "message": "На подразделении есть должности."})
    employees = db.scalars(select(Employee).where(Employee.org_unit_id == obj.id)).all()
    if employees:
        raise HTTPException(status_code=400, detail={"code": "org_unit_has_employees", "message": "На подразделении есть сотрудники."})
    db.delete(obj)


def delete_local_org_unit_cascade(db: Session, obj: OrgUnit) -> dict:
    assert_not_protected_code(obj.code)
    subtree_ids = _collect_subtree_ids(db, obj.id)
    blockers = _subtree_employee_blockers(db, subtree_ids)
    if blockers:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "org_unit_has_employees",
                "message": "В поддереве есть сотрудники — удаление невозможно.",
                "employees": blockers[:20],
            },
        )

    # Delete deepest first
    units = [db.get(OrgUnit, uid) for uid in subtree_ids]
    units = [u for u in units if u is not None]
    depth: dict[str, int] = {}

    def node_depth(u: OrgUnit) -> int:
        if u.id in depth:
            return depth[u.id]
        if not u.parent_id or u.parent_id not in {x.id for x in units}:
            depth[u.id] = 0
            return 0
        parent = next((x for x in units if x.id == u.parent_id), None)
        depth[u.id] = node_depth(parent) + 1 if parent else 0
        return depth[u.id]

    for u in units:
        node_depth(u)
    units.sort(key=lambda u: depth[u.id], reverse=True)

    positions_deleted = 0
    units_deleted = 0
    for u in units:
        for pos in db.scalars(select(Position).where(Position.org_unit_id == u.id)).all():
            emp = db.scalar(select(Employee).where(Employee.position_id == pos.id))
            if emp:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "org_unit_has_employees", "message": "На должности есть сотрудник."},
                )
            db.delete(pos)
            positions_deleted += 1
        db.delete(u)
        units_deleted += 1

    return {"units_deleted": units_deleted, "positions_deleted": positions_deleted}


def _template_codes(db: Session, template_code: str) -> set[str]:
    rows = db.scalars(
        select(TemplateOrgUnitRow.code).where(TemplateOrgUnitRow.template_code == template_code)
    ).all()
    return set(rows)


def _unique_template_code(db: Session, template_code: str, base: str) -> str:
    existing = _template_codes(db, template_code)
    candidate = f"{base}_COPY"
    if candidate not in existing:
        return candidate
    n = 2
    while True:
        candidate = f"{base}_COPY_{n}"
        if candidate not in existing:
            return candidate
        n += 1


@dataclass
class TemplateCloneResult:
    row: TemplateOrgUnitRow
    position_links_created: int
    sections_skipped: int


def clone_template_department(db: Session, source: TemplateOrgUnitRow) -> TemplateCloneResult:
    if source.unit_type != "department":
        raise HTTPException(
            status_code=400,
            detail={"code": "clone_source_not_department", "message": "Копировать можно только отделение (department)."},
        )
    assert_not_protected_code(source.code)

    new_code = _unique_template_code(db, source.template_code, source.code)
    sections_skipped = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == source.template_code,
            TemplateOrgUnitRow.parent_code == source.code,
        )
    ) or 0

    row = TemplateOrgUnitRow(
        id=new_id32(),
        template_code=source.template_code,
        code=new_code,
        name=f"{source.name} (Копия)",
        parent_code=source.parent_code,
        unit_type="department",
        sort_order=source.sort_order + 1,
    )
    db.add(row)
    db.flush()

    links_created = 0
    for link in db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == source.template_code,
            PositionDeptType.dept_type_code == source.code,
        )
    ).all():
        exists = db.get(PositionDeptType, (source.template_code, link.position_code, new_code))
        if exists:
            continue
        db.add(
            PositionDeptType(
                template_code=source.template_code,
                position_code=link.position_code,
                dept_type_code=new_code,
                is_primary=link.is_primary,
            )
        )
        links_created += 1

    db.flush()
    return TemplateCloneResult(row=row, position_links_created=links_created, sections_skipped=int(sections_skipped))


def template_delete_impact(db: Session, row: TemplateOrgUnitRow) -> dict:
    sections = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == row.template_code,
            TemplateOrgUnitRow.parent_code == row.code,
        )
    ) or 0
    position_links = db.scalar(
        select(func.count())
        .select_from(PositionDeptType)
        .where(
            PositionDeptType.template_code == row.template_code,
            PositionDeptType.dept_type_code == row.code,
        )
    ) or 0
    client_refs = db.scalar(
        select(func.count()).select_from(OrgUnit).where(OrgUnit.catalog_source_code == row.code)
    ) or 0
    return {
        "sections": int(sections),
        "position_links": int(position_links),
        "client_refs": int(client_refs),
    }


def delete_template_org_unit_leaf(db: Session, row: TemplateOrgUnitRow) -> None:
    assert_not_protected_code(row.code)
    children = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == row.template_code,
            TemplateOrgUnitRow.parent_code == row.code,
        )
    )
    if children:
        raise HTTPException(
            status_code=409,
            detail={"code": "template_org_unit_has_children", "message": "Есть дочерние узлы."},
        )
    db.delete(row)


def delete_template_org_unit_cascade(db: Session, row: TemplateOrgUnitRow) -> dict:
    assert_not_protected_code(row.code)
    impact = template_delete_impact(db, row)
    if impact["client_refs"] > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "template_org_unit_in_use",
                "message": "Узел используется у клиентов (catalog_source_code).",
                "affected": impact,
            },
        )

    sections = db.scalars(
        select(TemplateOrgUnitRow).where(
            TemplateOrgUnitRow.template_code == row.template_code,
            TemplateOrgUnitRow.parent_code == row.code,
        )
    ).all()
    for sec in sections:
        db.delete(sec)

    links = db.scalars(select(PositionDeptType).where(PositionDeptType.dept_type_code == row.code)).all()
    for link in links:
        db.delete(link)

    db.delete(row)
    return {
        "units_deleted": 1 + len(sections),
        "position_links_deleted": len(links),
        "sections_deleted": len(sections),
    }
