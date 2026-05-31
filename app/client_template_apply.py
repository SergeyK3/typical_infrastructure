"""Идемпотентное применение bundle-шаблона к существующему клиенту."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.client_catalog_sync import sync_global_regulations_to_client
from app.client_org_sync import sync_client_org_units_from_template
from app.client_template_dedup import dedup_client_template_entities
from app.models import Client, EnterpriseTemplate, OrgUnit, Position, PositionCatalog
from app.org_structures import list_positions_from_position_catalog
from app.position_deploy import (
    normalize_template_position_dept_links,
    select_position_dept_links_for_deploy,
)
from app.client_org_segment_sync import sync_segments_from_template
from app.org_unit_ops import resolve_org_unit_effective_segment
from app.template_org_resolve import resolve_template_structure
from app.utils import new_id32


def _position_exists_key(pos: Position) -> tuple[str, str]:
    catalog = (pos.position_catalog_code or pos.code or "").strip()
    return (pos.org_unit_id, catalog)


@dataclass
class ApplyTemplateResult:
    org_units_created: int = 0
    org_units_updated: int = 0
    org_units_skipped: int = 0
    positions_created: int = 0
    positions_skipped: int = 0
    regulations_created: int = 0
    positions_removed: int = 0
    template_dept_links_removed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "org_units_created": self.org_units_created,
            "org_units_updated": self.org_units_updated,
            "org_units_skipped": self.org_units_skipped,
            "positions_created": self.positions_created,
            "positions_skipped": self.positions_skipped,
            "regulations_created": self.regulations_created,
            "positions_removed": self.positions_removed,
            "template_dept_links_removed": self.template_dept_links_removed,
        }


def apply_template_to_client(
    db: Session,
    client_id: str,
    template_code: str,
    *,
    include_org_units: bool = True,
    include_positions: bool = True,
    include_regulations: bool = True,
    update_client_template: bool = True,
) -> ApplyTemplateResult:
    """
    Добавить отсутствующие узлы оргструктуры, должности и регламенты из шаблона.
    Существующие записи определяются по стабильным ключам, дубликаты не создаются.
    """
    client = db.get(Client, client_id)
    if not client:
        raise ValueError("client_not_found")

    template = db.scalar(
        select(EnterpriseTemplate).where(
            EnterpriseTemplate.code == template_code,
            EnterpriseTemplate.is_active == True,
        )
    )
    if not template:
        raise ValueError("template_not_found")

    if update_client_template and client.template_id != template.id:
        client.template_id = template.id

    result = ApplyTemplateResult()
    structure = resolve_template_structure(db, template_code)
    ids_by_code: dict[str, str] = {
        ou.code: ou.id
        for ou in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
    }

    if include_org_units:
        created, updated, skipped = sync_client_org_units_from_template(
            db, client_id, structure, ids_by_code
        )
        result.org_units_created = created
        result.org_units_updated = updated
        result.org_units_skipped = skipped

    if include_positions:
        result.template_dept_links_removed = normalize_template_position_dept_links(
            db, template_code
        )
        existing_positions = {
            _position_exists_key(p)
            for p in db.scalars(select(Position).where(Position.client_id == client_id)).all()
        }
        catalog_by_code = {
            r.position_code: r
            for r in db.scalars(
                select(PositionCatalog).where(
                    PositionCatalog.template_code == template_code,
                    PositionCatalog.is_active == True,
                )
            ).all()
        }
        dept_links = select_position_dept_links_for_deploy(db, template_code, structure)

        planned: list[tuple[dict, str]] = []
        for link in dept_links:
            catalog = catalog_by_code.get(link.position_code)
            ou_id = ids_by_code.get(link.dept_type_code)
            if not catalog or not ou_id:
                continue
            planned.append(
                (
                    {
                        "code": catalog.position_code,
                        "name": catalog.position_name_ru,
                        "function_code": catalog.function_code,
                        "position_level": catalog.position_level,
                        "is_managerial": catalog.is_managerial,
                        "is_active": True,
                    },
                    ou_id,
                )
            )

        if not planned:
            for p in list_positions_from_position_catalog(db, template_code):
                ou_id = ids_by_code.get(p["org_unit_code"])
                if ou_id:
                    planned.append((p, ou_id))

        for p, ou_id in planned:
            catalog_code = (p.get("code") or "").strip()
            if not catalog_code:
                continue
            key = (ou_id, catalog_code)
            if key in existing_positions:
                result.positions_skipped += 1
                continue
            ou = db.get(OrgUnit, ou_id)
            segment = resolve_org_unit_effective_segment(db, ou) if ou else None
            pos = Position(
                id=new_id32(),
                client_id=client_id,
                org_unit_id=ou_id,
                code=catalog_code,
                name=p["name"],
                grade=p.get("grade"),
                is_active=bool(p.get("is_active", True)),
                position_catalog_code=catalog_code,
                function_code=p.get("function_code"),
                position_level=p.get("position_level"),
                is_managerial=p.get("is_managerial"),
                is_detached=True,
                segment_code=segment,
            )
            db.add(pos)
            db.flush()
            existing_positions.add(key)
            result.positions_created += 1

    if include_regulations:
        result.regulations_created = sync_global_regulations_to_client(
            db, client_id, template_code=template_code
        )

    if include_org_units or include_positions or include_regulations:
        dedup_stats = dedup_client_template_entities(
            db, client_id, template_code=template_code
        )
        result.positions_removed = dedup_stats.positions_removed

    if include_org_units:
        sync_segments_from_template(
            db,
            client_id,
            template_code,
            update_positions=include_positions,
        )

    db.flush()
    return result
