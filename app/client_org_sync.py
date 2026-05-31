"""Синхронизация оргструктуры клиента с типовым шаблоном (unit_type, parent, имя)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import OrgUnit
from app.org_unit_ops import format_org_unit_name
from app.utils import new_id32


def _parent_would_cycle(db: Session, unit_id: str, new_parent_id: str | None) -> bool:
    if not new_parent_id or new_parent_id == unit_id:
        return new_parent_id == unit_id
    seen: set[str] = set()
    cur = db.get(OrgUnit, new_parent_id)
    while cur and cur.parent_id:
        if cur.parent_id == unit_id or cur.parent_id in seen:
            return True
        seen.add(cur.parent_id)
        cur = db.get(OrgUnit, cur.parent_id)
    return False


def sync_client_org_units_from_template(
    db: Session,
    client_id: str,
    structure: list[dict],
    ids_by_code: dict[str, str],
) -> tuple[int, int, int]:
    """
    Создать отсутствующие узлы и привести существующие к шаблону.
    Возвращает (created, updated, skipped).
    """
    created = 0
    updated = 0
    skipped = 0

    for spec in structure:
        code = spec["code"]
        parent_code = spec.get("parent_code")
        expected_parent_id = ids_by_code.get(parent_code) if parent_code else None
        if parent_code and not expected_parent_id:
            continue

        unit_type = spec["unit_type"]
        name = format_org_unit_name(spec["name"], unit_type)
        sort_order = int(spec.get("sort_order", 0))
        expected_segment = spec.get("segment_code") if unit_type == "department" else None

        if code in ids_by_code:
            ou = db.get(OrgUnit, ids_by_code[code])
            if not ou or ou.client_id != client_id:
                skipped += 1
                continue
            changed = False
            if ou.unit_type != unit_type:
                ou.unit_type = unit_type
                changed = True
            if ou.parent_id != expected_parent_id:
                if not _parent_would_cycle(db, ou.id, expected_parent_id):
                    ou.parent_id = expected_parent_id
                    changed = True
            if ou.name != name:
                ou.name = name
                changed = True
            if ou.sort_order != sort_order:
                ou.sort_order = sort_order
                changed = True
            if (ou.catalog_source_code or "") != code:
                ou.catalog_source_code = code
                changed = True
            if unit_type == "department" and ou.segment_code != expected_segment:
                ou.segment_code = expected_segment
                changed = True
            elif unit_type != "department" and ou.segment_code is not None:
                ou.segment_code = None
                changed = True
            if changed:
                updated += 1
                db.flush()
            else:
                skipped += 1
            continue

        ou = OrgUnit(
            id=new_id32(),
            client_id=client_id,
            code=code,
            name=name,
            parent_id=expected_parent_id,
            unit_type=unit_type,
            is_active=True,
            sort_order=sort_order,
            catalog_source_code=code,
            is_detached=True,
            segment_code=expected_segment,
        )
        db.add(ou)
        db.flush()
        ids_by_code[code] = ou.id
        created += 1

    return created, updated, skipped
