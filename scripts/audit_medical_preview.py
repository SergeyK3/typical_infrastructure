"""Audit: merged_medical_org_units vs DB vs API preview vs wizard display logic."""
from __future__ import annotations

import json
import sys
import urllib.request

from app.db import SessionLocal
from app.medical_template_data import merged_medical_org_units
from app.template_org_resolve import resolve_template_structure
from sqlalchemy import func, select

from app.models import TemplateOrgUnitRow


def _dept_codes(units: list) -> list[str]:
    return sorted(u["code"] if isinstance(u, dict) else u.code for u in units if (u.get("unit_type") if isinstance(u, dict) else u.unit_type) == "department")


def main() -> int:
    merged = merged_medical_org_units()
    print("=== 1. merged_medical_org_units() ===")
    print(f"  total: {len(merged)}")
    print(f"  departments ({len(_dept_codes(merged))}): {_dept_codes(merged)}")
    print(f"  sections: {sum(1 for u in merged if u['unit_type'] == 'section')}")

    db = SessionLocal()
    try:
        cnt = db.scalar(
            select(func.count()).select_from(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == "medical")
        )
        rows = db.scalars(
            select(TemplateOrgUnitRow).where(TemplateOrgUnitRow.template_code == "medical").order_by(TemplateOrgUnitRow.sort_order)
        ).all()
        structure = resolve_template_structure(db, "medical")
        print("\n=== 2. DB template_org_units (medical) ===")
        print(f"  rows in DB: {cnt}")
        print(f"  departments ({len(_dept_codes(rows))}): {_dept_codes(rows)}")
        print(f"  sections: {sum(1 for r in rows if r.unit_type == 'section')}")

        print("\n=== 3. resolve_template_structure('medical') [used by API] ===")
        print(f"  total: {len(structure)}")
        print(f"  departments ({len(_dept_codes(structure))}): {_dept_codes(structure)}")
        print(f"  sections: {sum(1 for s in structure if s['unit_type'] == 'section')}")
        print(f"  source: {'DB (template_org_units)' if cnt else 'fallback merged_medical_org_units()'}")

        merged_codes = {u["code"] for u in merged}
        db_codes = {r.code for r in rows}
        missing = sorted(merged_codes - db_codes)
        print(f"\n=== diff: canonical merged minus DB ===")
        print(f"  missing in DB: {len(missing)}")
        if missing:
            print(f"  codes: {missing}")
    finally:
        db.close()

    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    url = f"{base.rstrip('/')}/api/enterprise-templates/medical/structure-preview"
    print(f"\n=== 4. Live API GET {url} ===")
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        ou = data.get("org_units", [])
        print(f"  total org_units: {len(ou)}")
        print(f"  departments ({len(_dept_codes(ou))}): {_dept_codes(ou)}")
        print(f"  sections: {sum(1 for u in ou if u['unit_type'] == 'section')}")
        print(f"  counts.org_units from API: {data.get('counts', {}).get('org_units')}")
    except Exception as e:
        print(f"  unreachable: {e}")

    print("\n=== 5. Wizard (static/wizard/index.html) ===")
    print("  loadStructurePreview() renders ALL structurePreview.org_units without filter")
    print("  displayed count = API org_units.length (no client-side filtering)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
