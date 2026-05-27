"""
Связать DOCX/регламенты переименованных должностей с актуальными кодами в справочнике.

  HR_MANAGER (DOCX)              → HR_GENERALIST / REG_HR_GENERALIST_V1
  ACC_MATERIAL_ACCOUNTANT (DOCX) → ACC_ACCOUNTANT / REG_ACC_ACCOUNTANT_V1

Запуск из корня репозитория:
  python scripts/consolidate_renamed_regulations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text, update

from app.db import SessionLocal
from app.models import (
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    Position,
    PositionCatalog,
    PositionDeptType,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)

MERGES: list[tuple[str, str, str, str]] = [
    ("REG_HR_MANAGER_V1", "REG_HR_GENERALIST_V1", "HR_MANAGER", "HR_GENERALIST"),
    (
        "REG_ACC_MATERIAL_ACCOUNTANT_V1",
        "REG_ACC_ACCOUNTANT_V1",
        "ACC_MATERIAL_ACCOUNTANT",
        "ACC_ACCOUNTANT",
    ),
]

TEXT_FIELDS = (
    "regulation_name",
    "goal_summary",
    "ckp_short",
    "ckp_full",
    "google_doc_url",
    "instructions_folder_url",
    "notes",
)


def _prefer_source(target, source) -> None:
    for field in TEXT_FIELDS:
        src = (getattr(source, field) or "").strip()
        dst = (getattr(target, field) or "").strip()
        if src and (not dst or "Заполните" in dst or len(src) > len(dst)):
            setattr(target, field, getattr(source, field))


def _merge_global_regulation_kpis(db, template_code: str, old_code: str, new_code: str) -> int:
    moved = 0
    existing = {
        k.kpi_code
        for k in db.scalars(
            select(RegulationKpi).where(
                RegulationKpi.template_code == template_code,
                RegulationKpi.regulation_code == new_code,
            )
        ).all()
    }
    for k in db.scalars(
        select(RegulationKpi).where(
            RegulationKpi.template_code == template_code,
            RegulationKpi.regulation_code == old_code,
        )
    ).all():
        if k.kpi_code in existing:
            db.delete(k)
        else:
            k.regulation_code = new_code
            existing.add(k.kpi_code)
            moved += 1
    return moved


def _merge_global_instructions(db, template_code: str, old_code: str, new_code: str) -> int:
    moved = 0
    existing = {
        i.instruction_code
        for i in db.scalars(
            select(RegulationInstruction).where(
                RegulationInstruction.template_code == template_code,
                RegulationInstruction.regulation_code == new_code,
            )
        ).all()
    }
    for ins in db.scalars(
        select(RegulationInstruction).where(
            RegulationInstruction.template_code == template_code,
            RegulationInstruction.regulation_code == old_code,
        )
    ).all():
        if ins.instruction_code in existing:
            db.delete(ins)
        else:
            ins.regulation_code = new_code
            existing.add(ins.instruction_code)
            moved += 1
    return moved


def _delete_global_regulation(db, template_code: str, regulation_code: str) -> None:
    for rk in db.scalars(
        select(RegulationKpi).where(
            RegulationKpi.template_code == template_code,
            RegulationKpi.regulation_code == regulation_code,
        )
    ).all():
        db.delete(rk)
    for ri in db.scalars(
        select(RegulationInstruction).where(
            RegulationInstruction.template_code == template_code,
            RegulationInstruction.regulation_code == regulation_code,
        )
    ).all():
        db.delete(ri)
    obj = db.scalar(
        select(PositionRegulation).where(
            PositionRegulation.template_code == template_code,
            PositionRegulation.regulation_code == regulation_code,
        )
    )
    if obj:
        db.delete(obj)


def _merge_client_kpis(db, from_id: str, to_id: str) -> None:
    existing = {
        k.kpi_code
        for k in db.scalars(
            select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == to_id)
        ).all()
    }
    for k in db.scalars(
        select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == from_id)
    ).all():
        if k.kpi_code in existing:
            db.delete(k)
        else:
            k.client_regulation_id = to_id
            existing.add(k.kpi_code)


def _merge_client_instructions(db, from_id: str, to_id: str) -> None:
    existing = {
        i.instruction_code
        for i in db.scalars(
            select(ClientRegulationInstruction).where(
                ClientRegulationInstruction.client_regulation_id == to_id
            )
        ).all()
    }
    for ins in db.scalars(
        select(ClientRegulationInstruction).where(
            ClientRegulationInstruction.client_regulation_id == from_id
        )
    ).all():
        if ins.instruction_code in existing:
            db.delete(ins)
        else:
            ins.client_regulation_id = to_id
            existing.add(ins.instruction_code)


def _delete_client_regulation(db, reg_id: str) -> None:
    for rk in db.scalars(
        select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == reg_id)
    ).all():
        db.delete(rk)
    for ri in db.scalars(
        select(ClientRegulationInstruction).where(
            ClientRegulationInstruction.client_regulation_id == reg_id
        )
    ).all():
        db.delete(ri)
    obj = db.get(ClientPositionRegulation, reg_id)
    if obj:
        db.delete(obj)


def consolidate_client_regulations(db, old_code: str, new_code: str, new_pos: str) -> dict:
    stats = {"merged": 0, "repointed": 0, "deleted": 0}
    for cr in db.scalars(
        select(ClientPositionRegulation).where(
            (ClientPositionRegulation.regulation_code == old_code)
            | (ClientPositionRegulation.global_regulation_code == old_code)
        )
    ).all():
        dup = db.scalar(
            select(ClientPositionRegulation).where(
                ClientPositionRegulation.client_id == cr.client_id,
                ClientPositionRegulation.regulation_code == new_code,
            )
        )
        if dup and dup.id != cr.id:
            _merge_client_kpis(db, cr.id, dup.id)
            _merge_client_instructions(db, cr.id, dup.id)
            _prefer_source(dup, cr)
            _delete_client_regulation(db, cr.id)
            stats["merged"] += 1
        else:
            cr.regulation_code = new_code
            cr.global_regulation_code = new_code
            cr.position_code = new_pos
            stats["repointed"] += 1
    return stats


def consolidate_positions(db, old_pos: str, new_pos: str) -> dict:
    stats = {"repointed": 0, "deleted": 0}
    by_client: dict[str, list[Position]] = {}
    for p in db.scalars(select(Position).where(Position.position_catalog_code == old_pos)).all():
        by_client.setdefault(p.client_id, []).append(p)
    for client_id, old_rows in by_client.items():
        has_new = db.scalar(
            select(Position.id).where(
                Position.client_id == client_id,
                Position.position_catalog_code == new_pos,
            ).limit(1)
        )
        if has_new:
            for p in old_rows:
                db.delete(p)
                stats["deleted"] += 1
        else:
            for p in old_rows:
                p.position_catalog_code = new_pos
                stats["repointed"] += 1
    return stats


def _repoint_sql(db, table: str, old_pos: str, new_pos: str) -> int:
    r = db.execute(
        text(f"UPDATE {table} SET position_code = :new WHERE position_code = :old"),
        {"new": new_pos, "old": old_pos},
    )
    return r.rowcount or 0


def repoint_derived_position_codes(db, old_pos: str, new_pos: str) -> dict:
    stats = {}
    for table in ("kpi_templates", "competency_matrix", "kpi_matrix"):
        try:
            stats[table] = _repoint_sql(db, table, old_pos, new_pos)
        except Exception:
            stats[table] = 0
    return stats


def remove_catalog_position(db, old_pos: str) -> int:
    n = 0
    for row in db.scalars(select(PositionCatalog).where(PositionCatalog.position_code == old_pos)).all():
        db.delete(row)
        n += 1
    for row in db.scalars(select(PositionDeptType).where(PositionDeptType.position_code == old_pos)).all():
        db.delete(row)
        n += 1
    return n


def main() -> None:
    db = SessionLocal()
    report: list[str] = []
    try:
        for old_code, new_code, old_pos, new_pos in MERGES:
            report.append(f"=== {old_code} -> {new_code} ({old_pos} -> {new_pos}) ===")
            templates = {
                r.template_code
                for r in db.scalars(
                    select(PositionRegulation).where(
                        PositionRegulation.regulation_code.in_((old_code, new_code))
                    )
                ).all()
            }
            for tpl in sorted(templates):
                src = db.scalar(
                    select(PositionRegulation).where(
                        PositionRegulation.template_code == tpl,
                        PositionRegulation.regulation_code == old_code,
                    )
                )
                dst = db.scalar(
                    select(PositionRegulation).where(
                        PositionRegulation.template_code == tpl,
                        PositionRegulation.regulation_code == new_code,
                    )
                )
                if src and dst:
                    _prefer_source(dst, src)
                    kpis = _merge_global_regulation_kpis(db, tpl, old_code, new_code)
                    ins = _merge_global_instructions(db, tpl, old_code, new_code)
                    _delete_global_regulation(db, tpl, old_code)
                    report.append(f"  {tpl}: merged KPI={kpis}, instructions={ins}, deleted old global row")
                elif src and not dst:
                    src.regulation_code = new_code
                    src.position_code = new_pos
                    report.append(f"  {tpl}: repointed sole global row to {new_code}")

            cstats = consolidate_client_regulations(db, old_code, new_code, new_pos)
            report.append(f"  client regs: {cstats}")
            pstats = consolidate_positions(db, old_pos, new_pos)
            report.append(f"  positions: {pstats}")
            mstats = repoint_derived_position_codes(db, old_pos, new_pos)
            report.append(f"  matrix/templates repointed: {mstats}")
            removed = remove_catalog_position(db, old_pos)
            report.append(f"  catalog/dept rows removed for {old_pos}: {removed}")

        db.commit()
    finally:
        db.close()

    print("\n".join(report))
    print("\nDone.")


if __name__ == "__main__":
    main()
