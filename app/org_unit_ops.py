r"""Операции клонирования и каскадного удаления подразделений (локальные и глобальные)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Employee,
    OrgUnit,
    Position,
    PositionDeptType,
    PositionRegulation,
    TemplateOrgUnitRow,
)
from app.utils import new_id32

PROTECTED_ORG_CODES = frozenset({"company"})
VALID_UNIT_TYPES = frozenset({"company", "department", "section"})
LOG_GROUP_UNIT_TYPES = frozenset({"department", "section"})
SEGMENT_UNIT_TYPES = frozenset({"department"})


def assert_valid_unit_type(unit_type: str) -> None:
    if unit_type not in VALID_UNIT_TYPES:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_unit_type", "message": f"unit_type must be one of: {', '.join(sorted(VALID_UNIT_TYPES))}"},
        )


def format_org_unit_name(name: str, unit_type: str) -> str:
    """Отделения — UPPER; секции — первая буква заглавная, остальные строчные; company без изменений."""
    text = (name or "").strip()
    if not text:
        return text
    if unit_type == "department":
        return text.upper()
    if unit_type == "section":
        return text[0].upper() + text[1:].lower()
    return text


def normalize_org_unit_name(name: str, unit_type: str) -> str:
    """Алиас для единообразного именования при сохранении."""
    return format_org_unit_name(name, unit_type)


def normalize_template_log_group(unit_type: str, log_group: str | None) -> str | None:
    """log_group задаётся для отделений и секций, не для company."""
    lg = (log_group or "").strip() or None
    if unit_type in LOG_GROUP_UNIT_TYPES:
        return lg
    if lg:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "log_group_only_for_department",
                "message": "Логическая группа допустима только для отделений и секций.",
            },
        )
    return None


def normalize_template_segment_code(unit_type: str, segment_code: str | None) -> str | None:
    """segment_code задаётся только для отделений (department)."""
    seg = (segment_code or "").strip() or None
    if unit_type in SEGMENT_UNIT_TYPES:
        return seg
    if seg:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "segment_code_only_for_department",
                "message": "Сегмент деятельности допустим только для отделений (department).",
            },
        )
    return None


def effective_segment_from_specs(specs: list[dict], code: str) -> str | None:
    """Эффективный segment_code узла по списку spec (department — своё; section — от родителя)."""
    by_code = {s["code"]: s for s in specs if s.get("code")}
    spec = by_code.get(code)
    if not spec:
        return None
    if spec.get("unit_type") == "department":
        return spec.get("segment_code") or None
    parent = spec.get("parent_code")
    while parent:
        parent_spec = by_code.get(parent)
        if not parent_spec:
            break
        if parent_spec.get("unit_type") == "department":
            return parent_spec.get("segment_code") or None
        parent = parent_spec.get("parent_code")
    return None


def enrich_structure_with_effective_segments(specs: list[dict]) -> list[dict]:
    """Добавить effective_segment_code к каждому spec."""
    out: list[dict] = []
    for spec in specs:
        row = dict(spec)
        row["effective_segment_code"] = effective_segment_from_specs(specs, spec["code"])
        out.append(row)
    return out


def resolve_org_unit_effective_segment(db: Session, org_unit: OrgUnit) -> str | None:
    """Эффективный segment_code для клиентского узла (section → от department-предка)."""
    if org_unit.unit_type == "department":
        return org_unit.segment_code
    by_id = {
        u.id: u
        for u in db.scalars(select(OrgUnit).where(OrgUnit.client_id == org_unit.client_id)).all()
    }
    cur = org_unit
    seen: set[str] = set()
    while cur.parent_id and cur.parent_id not in seen:
        seen.add(cur.parent_id)
        parent = by_id.get(cur.parent_id)
        if not parent:
            break
        if parent.unit_type == "department":
            return parent.segment_code
        cur = parent
    return None


@dataclass
class ClientOrgEnrichContext:
    """Кэш для обогащения org_units (segment, log_group) в рамках одного запроса."""

    by_id: dict[str, OrgUnit]
    log_group_by_catalog_code: dict[str, str | None]

    @classmethod
    def build(cls, db: Session, client_id: str) -> ClientOrgEnrichContext:
        rows = db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
        return cls(
            by_id={u.id: u for u in rows},
            log_group_by_catalog_code=build_template_log_group_by_code(db, client_id),
        )


def effective_log_group_from_specs(specs: list[dict], code: str) -> str | None:
    """Эффективный log_group узла шаблона (department — своё; section — от department-предка)."""
    by_code = {s["code"]: s for s in specs if s.get("code")}
    spec = by_code.get(code)
    if not spec:
        return None
    if spec.get("unit_type") == "department":
        lg = (spec.get("log_group") or "").strip()
        return lg or None
    parent = spec.get("parent_code")
    while parent:
        parent_spec = by_code.get(parent)
        if not parent_spec:
            break
        if parent_spec.get("unit_type") == "department":
            lg = (parent_spec.get("log_group") or "").strip()
            return lg or None
        parent = parent_spec.get("parent_code")
    lg = (spec.get("log_group") or "").strip()
    return lg or None


def build_template_log_group_by_code(db: Session, client_id: str) -> dict[str, str | None]:
    """Код узла типового шаблона → effective log_group (для catalog_source_code клиента)."""
    from app.models import Client, EnterpriseTemplate
    from app.template_constants import DEFAULT_TEMPLATE_CODE
    from app.template_org_resolve import resolve_template_structure

    client = db.get(Client, client_id)
    if not client:
        return {}
    template_code = DEFAULT_TEMPLATE_CODE
    if client.template_id:
        tpl = db.get(EnterpriseTemplate, client.template_id)
        if tpl and tpl.is_active:
            template_code = tpl.code
    structure = resolve_template_structure(db, template_code)
    return {
        str(spec["code"]): effective_log_group_from_specs(structure, spec["code"])
        for spec in structure
        if spec.get("code")
    }


def _local_org_unit_log_group(org_unit: OrgUnit, ctx: ClientOrgEnrichContext) -> str | None:
    """log_group, заданный на клиентской строке (backfill), с наследованием section → department."""
    lg = (getattr(org_unit, "log_group", None) or "").strip()
    if lg:
        return lg
    if org_unit.unit_type == "section":
        cur = org_unit
        seen: set[str] = set()
        while cur.parent_id and cur.parent_id not in seen:
            seen.add(cur.parent_id)
            parent = ctx.by_id.get(cur.parent_id)
            if not parent:
                break
            plg = (getattr(parent, "log_group", None) or "").strip()
            if plg:
                return plg
            if parent.unit_type == "department":
                break
            cur = parent
    return None


def resolve_org_unit_effective_log_group(
    org_unit: OrgUnit,
    *,
    ctx: ClientOrgEnrichContext,
) -> str | None:
    """Эффективный log_group: локальный backfill → шаблон по catalog_source_code."""
    local = _local_org_unit_log_group(org_unit, ctx)
    if local:
        return local
    csc = (org_unit.catalog_source_code or "").strip()
    if csc and csc in ctx.log_group_by_catalog_code:
        return ctx.log_group_by_catalog_code[csc]
    code = (org_unit.code or "").strip()
    if code and code in ctx.log_group_by_catalog_code:
        return ctx.log_group_by_catalog_code[code]
    if org_unit.unit_type == "department":
        return None
    cur = org_unit
    seen: set[str] = set()
    while cur.parent_id and cur.parent_id not in seen:
        seen.add(cur.parent_id)
        parent = ctx.by_id.get(cur.parent_id)
        if not parent:
            break
        if parent.unit_type == "department":
            pcsc = (parent.catalog_source_code or "").strip()
            if pcsc and pcsc in ctx.log_group_by_catalog_code:
                return ctx.log_group_by_catalog_code[pcsc]
            return None
        cur = parent
    return None


def assert_not_protected_code(code: str) -> None:
    if code in PROTECTED_ORG_CODES:
        raise HTTPException(
            status_code=403,
            detail={"code": "org_unit_protected", "message": "Системный узел нельзя удалить, переименовать или клонировать."},
        )


def rename_template_org_unit_code(db: Session, row: TemplateOrgUnitRow, new_code: str) -> None:
    """Переименовать код узла шаблона и обновить ссылки (дети, должности, регламенты)."""
    new_code = new_code.strip()
    if not new_code:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_org_code", "message": "Код узла не может быть пустым."},
        )
    if new_code == row.code:
        return
    assert_not_protected_code(row.code)
    if new_code in PROTECTED_ORG_CODES:
        raise HTTPException(
            status_code=403,
            detail={"code": "org_unit_protected", "message": "Код «company» зарезервирован."},
        )
    dup = db.scalar(
        select(func.count())
        .select_from(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == row.template_code,
            TemplateOrgUnitRow.code == new_code,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail="template_org_unit_code_exists")

    old_code = row.code
    tpl = row.template_code

    db.execute(
        update(TemplateOrgUnitRow)
        .where(
            TemplateOrgUnitRow.template_code == tpl,
            TemplateOrgUnitRow.parent_code == old_code,
        )
        .values(parent_code=new_code)
    )

    links = db.scalars(
        select(PositionDeptType).where(
            PositionDeptType.template_code == tpl,
            PositionDeptType.dept_type_code == old_code,
        )
    ).all()
    for link in links:
        if db.get(PositionDeptType, (tpl, link.position_code, new_code)):
            db.delete(link)
            continue
        db.add(
            PositionDeptType(
                template_code=tpl,
                position_code=link.position_code,
                dept_type_code=new_code,
                is_primary=link.is_primary,
            )
        )
        db.delete(link)

    db.execute(
        update(PositionRegulation)
        .where(
            PositionRegulation.template_code == tpl,
            PositionRegulation.dept_type_code == old_code,
        )
        .values(dept_type_code=new_code)
    )

    row.code = new_code


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
    copy_name = format_org_unit_name(copy_name, "department")
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


def clone_local_section(
    db: Session,
    source: OrgUnit,
    *,
    name_suffix: str = "Копия",
    new_code: str | None = None,
) -> LocalCloneResult:
    if source.unit_type != "section":
        raise HTTPException(
            status_code=400,
            detail={"code": "clone_source_not_section", "message": "Копировать можно только секцию (section)."},
        )
    assert_not_protected_code(source.code)

    parent_id = source.parent_id
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

    copy_name = source.name if name_suffix in source.name else f"{source.name} ({name_suffix})"
    copy_name = format_org_unit_name(copy_name, "section")
    new_ou = OrgUnit(
        id=new_id32(),
        client_id=source.client_id,
        code=code,
        name=copy_name,
        parent_id=parent_id,
        unit_type="section",
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
    return LocalCloneResult(org_unit=new_ou, positions_created=positions_created, sections_skipped=0)


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
        name=format_org_unit_name(f"{source.name} (Копия)", "department"),
        parent_code=source.parent_code,
        unit_type="department",
        sort_order=source.sort_order + 1,
        log_group=source.log_group,
        segment_code=source.segment_code,
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
                is_primary=False,
            )
        )
        links_created += 1

    db.flush()
    return TemplateCloneResult(row=row, position_links_created=links_created, sections_skipped=int(sections_skipped))


def clone_template_section(db: Session, source: TemplateOrgUnitRow) -> TemplateCloneResult:
    if source.unit_type != "section":
        raise HTTPException(
            status_code=400,
            detail={"code": "clone_source_not_section", "message": "Копировать можно только секцию (section)."},
        )
    assert_not_protected_code(source.code)

    new_code = _unique_template_code(db, source.template_code, source.code)
    row = TemplateOrgUnitRow(
        id=new_id32(),
        template_code=source.template_code,
        code=new_code,
        name=format_org_unit_name(f"{source.name} (Копия)", "section"),
        parent_code=source.parent_code,
        unit_type="section",
        sort_order=source.sort_order + 1,
        log_group=source.log_group,
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
                is_primary=False,
            )
        )
        links_created += 1

    db.flush()
    return TemplateCloneResult(row=row, position_links_created=links_created, sections_skipped=0)


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
