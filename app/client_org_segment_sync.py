"""Синхронизация segment_code из типовой оргструктуры в локальные org_units и должности."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OrgUnit, Position
from app.org_unit_ops import resolve_org_unit_effective_segment
from app.template_org_resolve import resolve_template_structure


@dataclass
class SegmentSyncResult:
    org_units_updated: int = 0
    positions_updated: int = 0


def sync_segments_from_template(
    db: Session,
    client_id: str,
    template_code: str,
    *,
    update_positions: bool = True,
) -> SegmentSyncResult:
    """
    Перенести segment_code из шаблона в клиентские отделения (по catalog_source_code).
    Для должностей — проставить effective segment от org_unit (перезаписывает segment_code).
    """
    structure = resolve_template_structure(db, template_code)
    by_code = {s["code"]: s for s in structure}
    result = SegmentSyncResult()

    org_units = db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
    for ou in org_units:
        if not ou.catalog_source_code:
            continue
        spec = by_code.get(ou.catalog_source_code)
        if not spec:
            continue
        if ou.unit_type == "department":
            expected = spec.get("segment_code")
            if ou.segment_code != expected:
                ou.segment_code = expected
                result.org_units_updated += 1
        elif ou.unit_type == "section" and ou.segment_code is not None:
            ou.segment_code = None
            result.org_units_updated += 1

    if update_positions:
        by_id = {u.id: u for u in org_units}
        positions = db.scalars(select(Position).where(Position.client_id == client_id)).all()
        for pos in positions:
            ou = by_id.get(pos.org_unit_id)
            if not ou:
                continue
            expected = resolve_org_unit_effective_segment(db, ou)
            if pos.segment_code != expected:
                pos.segment_code = expected
                result.positions_updated += 1

    if result.org_units_updated or result.positions_updated:
        db.flush()
    return result
