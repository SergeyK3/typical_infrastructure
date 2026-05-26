"""Удаление дубликатов сущностей клиента после повторного применения шаблона."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    Employee,
    OrgUnit,
    Position,
)


def _position_catalog_key(pos: Position) -> str:
    return (pos.position_catalog_code or pos.code or "").strip()


@dataclass
class DedupStats:
    org_units_updated: int = 0
    org_units_removed: int = 0
    positions_removed: int = 0
    regulations_removed: int = 0
    regulation_kpis_removed: int = 0
    regulation_instructions_removed: int = 0
    employees_reassigned: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "org_units_updated": self.org_units_updated,
            "org_units_removed": self.org_units_removed,
            "positions_removed": self.positions_removed,
            "regulations_removed": self.regulations_removed,
            "regulation_kpis_removed": self.regulation_kpis_removed,
            "regulation_instructions_removed": self.regulation_instructions_removed,
            "employees_reassigned": self.employees_reassigned,
            "details": self.details,
        }


def _delete_client_regulation(db: Session, reg: ClientPositionRegulation, *, dry_run: bool) -> None:
    if dry_run:
        return
    for rk in db.scalars(
        select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == reg.id)
    ).all():
        db.delete(rk)
    for ri in db.scalars(
        select(ClientRegulationInstruction).where(
            ClientRegulationInstruction.client_regulation_id == reg.id
        )
    ).all():
        db.delete(ri)
    db.delete(reg)


def dedup_client_org_units(db: Session, client_id: str, *, dry_run: bool = False) -> int:
    """Оставить один узел на код подразделения (самый ранний по created_at)."""
    rows = list(
        db.scalars(
            select(OrgUnit)
            .where(OrgUnit.client_id == client_id)
            .order_by(OrgUnit.created_at.asc(), OrgUnit.id.asc())
        ).all()
    )
    groups: dict[str, list[OrgUnit]] = defaultdict(list)
    for ou in rows:
        code = (ou.code or "").strip()
        if code:
            groups[code].append(ou)

    removed = 0
    for group in groups.values():
        if len(group) <= 1:
            continue
        keeper = group[0]
        for dup in group[1:]:
            for child in db.scalars(select(OrgUnit).where(OrgUnit.parent_id == dup.id)).all():
                if not dry_run:
                    child.parent_id = keeper.id
            for pos in db.scalars(select(Position).where(Position.org_unit_id == dup.id)).all():
                if not dry_run:
                    pos.org_unit_id = keeper.id
            for emp in db.scalars(select(Employee).where(Employee.org_unit_id == dup.id)).all():
                if not dry_run:
                    emp.org_unit_id = keeper.id
            if not dry_run:
                db.delete(dup)
            removed += 1
    return removed


def dedup_client_positions(db: Session, client_id: str, *, dry_run: bool = False) -> tuple[int, int]:
    """Оставить одну должность на пару (подразделение, код каталога/должности)."""
    rows = list(
        db.scalars(
            select(Position)
            .where(Position.client_id == client_id)
            .order_by(Position.created_at.asc(), Position.id.asc())
        ).all()
    )
    groups: dict[tuple[str, str], list[Position]] = defaultdict(list)
    for pos in rows:
        key = _position_catalog_key(pos)
        if key:
            groups[(pos.org_unit_id, key)].append(pos)

    removed = 0
    reassigned = 0
    for group in groups.values():
        if len(group) <= 1:
            continue
        keeper = group[0]
        for dup in group[1:]:
            for emp in db.scalars(select(Employee).where(Employee.position_id == dup.id)).all():
                if not dry_run:
                    emp.position_id = keeper.id
                reassigned += 1
            if not dry_run:
                db.delete(dup)
            removed += 1
    return removed, reassigned


def dedup_client_regulations(db: Session, client_id: str, *, dry_run: bool = False) -> int:
    """Удалить дубликаты регламентов по коду, global-коду и слоту (должность + отделение + версия)."""
    rows = list(
        db.scalars(
            select(ClientPositionRegulation)
            .where(ClientPositionRegulation.client_id == client_id)
            .order_by(ClientPositionRegulation.created_at.asc(), ClientPositionRegulation.id.asc())
        ).all()
    )
    removed_ids: set[str] = set()

    def _drop_duplicates(groups: dict[Any, list[ClientPositionRegulation]]) -> None:
        nonlocal removed_ids
        for group in groups.values():
            if len(group) <= 1:
                continue
            keeper = group[0]
            for dup in group[1:]:
                if dup.id in removed_ids or keeper.id in removed_ids:
                    continue
                _delete_client_regulation(db, dup, dry_run=dry_run)
                removed_ids.add(dup.id)

    by_code: dict[str, list[ClientPositionRegulation]] = defaultdict(list)
    by_global: dict[str, list[ClientPositionRegulation]] = defaultdict(list)
    by_slot: dict[tuple[str, str, str], list[ClientPositionRegulation]] = defaultdict(list)
    for reg in rows:
        by_code[reg.regulation_code.strip()].append(reg)
        glob = (reg.global_regulation_code or "").strip()
        if glob:
            by_global[glob].append(reg)
        by_slot[(reg.position_code.strip(), reg.dept_type_code.strip(), reg.version_no.strip())].append(reg)

    _drop_duplicates(by_code)
    _drop_duplicates(by_global)
    _drop_duplicates(by_slot)
    return len(removed_ids)


def dedup_client_regulation_children(db: Session, client_id: str, *, dry_run: bool = False) -> tuple[int, int]:
    """Удалить повторяющиеся KPI и инструкции внутри клиентских регламентов."""
    reg_ids = db.scalars(
        select(ClientPositionRegulation.id).where(ClientPositionRegulation.client_id == client_id)
    ).all()
    kpis_removed = 0
    instructions_removed = 0
    for reg_id in reg_ids:
        kpi_groups: dict[str, list[ClientRegulationKpi]] = defaultdict(list)
        for kpi in db.scalars(
            select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == reg_id)
        ).all():
            kpi_groups[kpi.kpi_code.strip()].append(kpi)
        for group in kpi_groups.values():
            if len(group) <= 1:
                continue
            for dup in group[1:]:
                if not dry_run:
                    db.delete(dup)
                kpis_removed += 1

        ins_groups: dict[str, list[ClientRegulationInstruction]] = defaultdict(list)
        for ins in db.scalars(
            select(ClientRegulationInstruction).where(
                ClientRegulationInstruction.client_regulation_id == reg_id
            )
        ).all():
            ins_groups[ins.instruction_code.strip()].append(ins)
        for group in ins_groups.values():
            if len(group) <= 1:
                continue
            for dup in group[1:]:
                if not dry_run:
                    db.delete(dup)
                instructions_removed += 1
    return kpis_removed, instructions_removed


def dedup_misplaced_positions(
    db: Session, client_id: str, template_code: str, *, dry_run: bool = False
) -> tuple[int, int]:
    """Удалить должности в «чужих» отделениях — оставить одну на код каталога в primary-отделении шаблона."""
    from app.position_deploy import select_position_dept_links_for_deploy
    from app.template_org_resolve import resolve_template_structure

    structure = resolve_template_structure(db, template_code)
    canonical: dict[str, str] = {
        link.position_code: link.dept_type_code
        for link in select_position_dept_links_for_deploy(db, template_code, structure)
    }
    if not canonical:
        return 0, 0

    ou_by_code = {
        ou.code: ou.id
        for ou in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
    }
    removed = 0
    reassigned = 0
    by_catalog: dict[str, list[Position]] = defaultdict(list)
    for pos in db.scalars(select(Position).where(Position.client_id == client_id)).all():
        key = _position_catalog_key(pos)
        if key:
            by_catalog[key].append(pos)

    for catalog_code, dept_code in canonical.items():
        expected_ou = ou_by_code.get(dept_code)
        if not expected_ou:
            continue
        group = by_catalog.get(catalog_code, [])
        if not group:
            continue
        keeper = next((p for p in group if p.org_unit_id == expected_ou), None)
        for pos in group:
            if pos.org_unit_id == expected_ou:
                continue
            if keeper is None:
                keeper = sorted(group, key=lambda p: p.created_at)[0]
            if pos.id == keeper.id:
                continue
            for emp in db.scalars(select(Employee).where(Employee.position_id == pos.id)).all():
                if not dry_run:
                    emp.position_id = keeper.id
                reassigned += 1
            if not dry_run:
                db.delete(pos)
            removed += 1
    return removed, reassigned


def dedup_client_template_entities(
    db: Session, client_id: str, *, dry_run: bool = False, template_code: str | None = None
) -> DedupStats:
    """Полная дедупликация сущностей клиента, созданных из шаблона."""
    from app.template_bundle_clone import resolve_client_template_code

    from app.client_org_sync import sync_client_org_units_from_template
    from app.template_org_resolve import resolve_template_structure

    stats = DedupStats()
    tpl = template_code or resolve_client_template_code(db, client_id)
    structure = resolve_template_structure(db, tpl)
    ids_by_code = {
        ou.code: ou.id
        for ou in db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
    }
    if not dry_run:
        _, updated, _ = sync_client_org_units_from_template(
            db, client_id, structure, ids_by_code
        )
        stats.org_units_updated = updated
    stats.org_units_removed = dedup_client_org_units(db, client_id, dry_run=dry_run)
    misplaced, reassign_mis = dedup_misplaced_positions(
        db, client_id, tpl, dry_run=dry_run
    )
    stats.positions_removed += misplaced
    stats.employees_reassigned += reassign_mis
    pos_removed, reassigned = dedup_client_positions(db, client_id, dry_run=dry_run)
    stats.positions_removed += pos_removed
    stats.employees_reassigned += reassigned
    stats.regulations_removed = dedup_client_regulations(db, client_id, dry_run=dry_run)
    kpis_removed, ins_removed = dedup_client_regulation_children(db, client_id, dry_run=dry_run)
    stats.regulation_kpis_removed = kpis_removed
    stats.regulation_instructions_removed = ins_removed
    if not dry_run:
        db.flush()
    return stats


def dedup_all_clients(db: Session, *, dry_run: bool = False) -> dict[str, dict[str, Any]]:
    from app.models import Client

    out: dict[str, dict[str, Any]] = {}
    for client in db.scalars(select(Client)).all():
        stats = dedup_client_template_entities(db, client.id, dry_run=dry_run)
        out[client.code] = stats.as_dict()
    if not dry_run:
        db.flush()
    return out
