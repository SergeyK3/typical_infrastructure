#!/usr/bin/env python3
"""Backfill log_group (slug из group_id Excel) для template_org_units и клиентских org_units."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db import SessionLocal
from app.medical_org_groups import log_group_label
from app.medical_template_excel import (
    default_medical_org_excel_path,
    load_medical_org_excel,
    resolve_log_group_for_client_unit,
)
from app.models import Client, OrgUnit, TemplateOrgUnitRow
from app.template_constants import MEDICAL_TEMPLATE_CODE

DEFAULT_MMC_CLIENT_ID = "264876490aa64816aa238f8e49546c3d"


@dataclass
class BackfillStats:
    found: int = 0
    updated: int = 0
    skipped: int = 0
    unmatched: int = 0
    name_fallback: list[str] = field(default_factory=list)
    unmatched_codes: list[str] = field(default_factory=list)

    def merge(self, other: BackfillStats) -> None:
        self.found += other.found
        self.updated += other.updated
        self.skipped += other.skipped
        self.unmatched += other.unmatched
        self.name_fallback.extend(other.name_fallback)
        self.unmatched_codes.extend(other.unmatched_codes)


def sync_template_org_units(
    db,
    excel,
    *,
    apply: bool,
) -> BackfillStats:
    stats = BackfillStats()
    rows = db.scalars(
        select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == MEDICAL_TEMPLATE_CODE)
    ).all()
    stats.found = len(rows)
    for row in rows:
        ex = excel.by_code.get(row.code)
        if not ex or not ex.log_group:
            if row.unit_type not in ("company",):
                stats.unmatched += 1
                stats.unmatched_codes.append(row.code)
            else:
                stats.skipped += 1
            continue
        if row.log_group == ex.log_group:
            stats.skipped += 1
            continue
        stats.updated += 1
        if apply:
            row.log_group = ex.log_group
            db.add(row)
    if apply and stats.updated:
        db.commit()
    return stats


def backfill_client_org_units(
    db,
    client_id: str,
    excel,
    *,
    apply: bool,
) -> BackfillStats:
    stats = BackfillStats()
    client = db.get(Client, client_id)
    if not client:
        raise ValueError(f"client_not_found:{client_id}")

    rows = db.scalars(select(OrgUnit).where(OrgUnit.client_id == client_id)).all()
    stats.found = len(rows)
    excel.name_fallback_matches = []

    for row in rows:
        expected, kind = resolve_log_group_for_client_unit(
            code=row.code,
            catalog_source_code=row.catalog_source_code,
            name=row.name,
            unit_type=row.unit_type,
            excel=excel,
        )
        if kind == "skip_root":
            stats.skipped += 1
            continue
        if kind == "name_fallback":
            stats.name_fallback.append(row.code)
        if not expected:
            stats.unmatched += 1
            stats.unmatched_codes.append(row.code)
            continue
        current = (getattr(row, "log_group", None) or "").strip() or None
        if current == expected:
            stats.skipped += 1
            continue
        stats.updated += 1
        if apply:
            row.log_group = expected
            db.add(row)

    if apply and stats.updated:
        db.commit()
    return stats


def _print_stats(title: str, stats: BackfillStats) -> None:
    print(f"=== {title} ===")
    print(f"  found:      {stats.found}")
    print(f"  updated:    {stats.updated}")
    print(f"  skipped:    {stats.skipped}")
    print(f"  unmatched:  {stats.unmatched}")
    if stats.name_fallback:
        print(f"  name_fallback ({len(stats.name_fallback)}): {', '.join(stats.name_fallback[:20])}")
    if stats.unmatched_codes:
        sample = stats.unmatched_codes[:30]
        print(f"  unmatched codes ({len(stats.unmatched_codes)}): {', '.join(sample)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-id",
        default=DEFAULT_MMC_CLIENT_ID,
        help=f"client_id (default: ММЦ Астана {DEFAULT_MMC_CLIENT_ID})",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=None,
        help="Путь к template_org_medical.xlsx",
    )
    parser.add_argument(
        "--sync-template",
        action="store_true",
        help="Обновить template_org_units (medical) из Excel",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать изменения (по умолчанию dry-run)",
    )
    args = parser.parse_args()

    excel_path = args.excel or default_medical_org_excel_path()
    excel = load_medical_org_excel(excel_path)
    print(f"Excel: {excel_path}")
    print("Groups (group_id -> label -> log_group slug):")
    for gid, label in sorted(excel.group_labels.items(), key=lambda x: int(x[0])):
        from app.medical_org_groups import group_id_to_log_group

        slug = group_id_to_log_group(gid)
        print(f"  {gid}: {label} -> {slug} ({log_group_label(slug)})")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print()

    db = SessionLocal()
    try:
        if args.sync_template:
            tpl_stats = sync_template_org_units(db, excel, apply=args.apply)
            _print_stats("template_org_units (medical)", tpl_stats)
            print()

        client = db.get(Client, args.client_id)
        if not client:
            print(f"WARNING: client_not_found:{args.client_id} — client backfill skipped")
        else:
            client_stats = backfill_client_org_units(
                db, args.client_id, excel, apply=args.apply
            )
            _print_stats(f"client org_units ({client.name})", client_stats)
    finally:
        db.close()

    if not args.apply:
        print()
        print("Dry-run: изменения не сохранены. Для записи добавьте --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
