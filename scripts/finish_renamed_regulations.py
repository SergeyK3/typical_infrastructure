"""Финализация переименованных регламентов: sync из DOCX + прокидка в клиентские копии."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ClientPositionRegulation, PositionRegulation
from app.universal_seed import apply_regulation_enrichment_json
import scripts.sync_global_regulations_from_sources as sync_mod

TEXT_FIELDS = (
    "regulation_name",
    "goal_summary",
    "ckp_short",
    "ckp_full",
    "google_doc_url",
    "instructions_folder_url",
    "notes",
)

CANONICAL = ("REG_HR_GENERALIST_V1", "REG_ACC_ACCOUNTANT_V1")


def propagate_clients(db) -> int:
    updated = 0
    globals_ = {
        g.regulation_code: g
        for g in db.scalars(
            select(PositionRegulation).where(PositionRegulation.regulation_code.in_(CANONICAL))
        ).all()
    }
    by_code: dict[str, PositionRegulation] = {}
    for g in globals_.values():
        cur = by_code.get(g.regulation_code)
        if not cur or g.template_code == "default":
            by_code[g.regulation_code] = g

    for cr in db.scalars(select(ClientPositionRegulation)).all():
        code = (cr.global_regulation_code or cr.regulation_code).strip()
        glob = by_code.get(code)
        if not glob:
            continue
        changed = False
        for field in TEXT_FIELDS:
            gval = getattr(glob, field)
            if gval and (getattr(cr, field) or "").strip() != (gval or "").strip():
                setattr(cr, field, gval)
                changed = True
        if changed:
            updated += 1
    return updated


def main() -> None:
    db = SessionLocal()
    try:
        n_enrich = apply_regulation_enrichment_json(db)
        url_map = sync_mod.load_url_maps()
        by_pos = sync_mod.collect_parsed(url_map)
        report = sync_mod.SyncReport()
        for tpl in ("default", "hosp"):
            sync_mod.sync_template(db, tpl, by_pos, report)
        client_updated = propagate_clients(db)
        db.commit()
    finally:
        db.close()

    print(f"Enrichment rows: {n_enrich}")
    print(f"Regulations updated: {len(report.regulations_updated)}")
    print(f"Regulation-KPI links added: {len(report.regulation_kpis_linked)}")
    print(f"Skills added: {len(report.skills_added)}")
    print(f"KPI matrix rows added: {len(report.kpi_matrix_added)}")
    print(f"Name fixes: {len(report.name_fixes)}")
    print(f"Client regulations synced: {client_updated}")
    if report.name_fixes:
        for item in report.name_fixes:
            print(f"  name: {item['template']} {item['position']}: {item['was']!r} -> {item['now']!r}")


if __name__ == "__main__":
    main()
