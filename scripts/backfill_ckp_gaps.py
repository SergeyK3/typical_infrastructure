"""Разовое заполнение пропусков ЦКП: ссылки, тексты из Google Doc, удаление копии."""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    ClientPositionRegulation,
    ClientRegulationInstruction,
    ClientRegulationKpi,
    PositionRegulation,
    RegulationInstruction,
    RegulationKpi,
)
import scripts.sync_global_regulations_from_sources as sync

URLS = {
    "REG_HR_GENERALIST_V1": "https://docs.google.com/document/d/1BKnjtODOLHAYyrYnXMl_hHI6lgtjbIouuwr3UyZdPiA/edit?usp=sharing",
    "REG_ACC_ACCOUNTANT_V1": "https://docs.google.com/document/d/1kySyFsCmkGJMkmK35iBoHEw5d87YlCDsrndjrOefwZY/edit?usp=sharing",
}

SECTION_RE = re.compile(r"^(\d+)\.\s+")


def _fetch_gdoc_text(doc_id: str) -> str:
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")


def _sections(paras: list[str]) -> dict[int, list[str]]:
    sections: dict[int, list[str]] = {}
    current: int | None = None
    for line in paras:
        m = SECTION_RE.match(line)
        if m:
            current = int(m.group(1))
            sections.setdefault(current, []).append(line)
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def parse_gdoc_text(text: str) -> dict[str, str | None]:
    paras = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sec = _sections(paras)
    goal_parts = sec.get(2, [])
    goal_summary = " ".join(goal_parts[1:])[:512] if len(goal_parts) > 1 else None
    s3 = sec.get(3, [])
    ckp_short = (s3[1] if len(s3) > 1 else (s3[0] if s3 else None)) or None
    if ckp_short:
        ckp_short = ckp_short[:512]
    ckp_chunks: list[str] = []
    for n in (3, 4, 5):
        if n in sec:
            ckp_chunks.extend(sec[n])
    ckp_full = "\n\n".join(ckp_chunks) if ckp_chunks else None
    derived = sync._derive_ckp_short(ckp_full, ckp_short)
    if derived:
        ckp_short = derived
    return {
        "goal_summary": goal_summary,
        "ckp_short": ckp_short,
        "ckp_full": ckp_full,
    }


def _doc_id(url: str) -> str:
    m = re.search(r"/document/d/([^/]+)", url)
    if not m:
        raise ValueError(f"bad google doc url: {url}")
    return m.group(1)


def delete_global_regulation(db, regulation_code: str) -> int:
    n = 0
    for obj in db.scalars(
        select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code)
    ).all():
        for rk in db.scalars(
            select(RegulationKpi).where(
                RegulationKpi.template_code == obj.template_code,
                RegulationKpi.regulation_code == regulation_code,
            )
        ).all():
            db.delete(rk)
            n += 1
        for ri in db.scalars(
            select(RegulationInstruction).where(
                RegulationInstruction.template_code == obj.template_code,
                RegulationInstruction.regulation_code == regulation_code,
            )
        ).all():
            db.delete(ri)
            n += 1
        db.delete(obj)
        n += 1
    return n


def delete_client_by_code(db, regulation_code: str) -> int:
    n = 0
    for obj in db.scalars(
        select(ClientPositionRegulation).where(
            (ClientPositionRegulation.regulation_code == regulation_code)
            | (ClientPositionRegulation.global_regulation_code == regulation_code)
        )
    ).all():
        for rk in db.scalars(
            select(ClientRegulationKpi).where(ClientRegulationKpi.client_regulation_id == obj.id)
        ).all():
            db.delete(rk)
        for ri in db.scalars(
            select(ClientRegulationInstruction).where(
                ClientRegulationInstruction.client_regulation_id == obj.id
            )
        ).all():
            db.delete(ri)
        db.delete(obj)
        n += 1
    return n


def apply_text_fields(reg, fields: dict[str, str | None], url: str) -> list[str]:
    changed: list[str] = []
    reg.google_doc_url = url
    changed.append("google_doc_url")
    for key in ("goal_summary", "ckp_short", "ckp_full"):
        val = fields.get(key)
        if val:
            setattr(reg, key, val)
            changed.append(key)
    return changed


def backfill_client_from_global(db, regulation_code: str) -> int:
    updated = 0
    globals_ = {
        g.regulation_code: g
        for g in db.scalars(
            select(PositionRegulation).where(PositionRegulation.regulation_code == regulation_code)
        ).all()
    }
    if not globals_:
        return 0
    glob = next(iter(globals_.values()))
    for cr in db.scalars(
        select(ClientPositionRegulation).where(
            (ClientPositionRegulation.regulation_code == regulation_code)
            | (ClientPositionRegulation.global_regulation_code == regulation_code)
        )
    ).all():
        changed = False
        if url := glob.google_doc_url:
            if cr.google_doc_url != url:
                cr.google_doc_url = url
                changed = True
        for key in ("goal_summary", "ckp_full", "ckp_short"):
            gval = getattr(glob, key)
            if gval and not (getattr(cr, key) or "").strip():
                setattr(cr, key, gval)
                changed = True
        if changed:
            updated += 1
    return updated


def list_ckp_gaps(db) -> tuple[list, list]:
    def gap_rows(model, extra_cols=()):
        cols = ["regulation_code", "position_code"]
        q = select(model).where(model.is_current == True)
        rows = db.scalars(q).all()
        out = []
        for r in rows:
            if not (r.ckp_short or "").strip() or not (r.ckp_full or "").strip():
                item = {
                    "regulation_code": r.regulation_code,
                    "position_code": r.position_code,
                }
                if hasattr(r, "template_code"):
                    item["template_code"] = r.template_code
                if hasattr(r, "client_id"):
                    item["client_id"] = r.client_id
                out.append(item)
        return out

    return gap_rows(PositionRegulation), gap_rows(ClientPositionRegulation)


def main() -> None:
    db = SessionLocal()
    report: dict = {"actions": [], "client_gaps_before": [], "remaining": {}}
    try:
        _, client_before = list_ckp_gaps(db)
        report["client_gaps_before"] = client_before

        deleted_global = delete_global_regulation(db, "REG_ACC_ACCOUNTANT_V1_COPY")
        deleted_client = delete_client_by_code(db, "REG_ACC_ACCOUNTANT_V1_COPY")
        report["actions"].append(
            f"deleted REG_ACC_ACCOUNTANT_V1_COPY: global={deleted_global}, client={deleted_client}"
        )

        parsed_cache: dict[str, dict] = {}
        for reg_code, url in URLS.items():
            doc_id = _doc_id(url)
            if doc_id not in parsed_cache:
                parsed_cache[doc_id] = parse_gdoc_text(_fetch_gdoc_text(doc_id))
            fields = parsed_cache[doc_id]
            updated_rows = []
            for reg in db.scalars(
                select(PositionRegulation).where(PositionRegulation.regulation_code == reg_code)
            ).all():
                changed = apply_text_fields(reg, fields, url)
                updated_rows.append(f"{reg.template_code}:{','.join(changed)}")
            client_n = backfill_client_from_global(db, reg_code)
            report["actions"].append(
                f"updated {reg_code}: global rows {updated_rows}, client backfilled {client_n}"
            )

        db.commit()

        global_after, client_after = list_ckp_gaps(db)
        report["remaining"] = {"global": global_after, "client": client_after}
    finally:
        db.close()

    print("=== CLIENT gaps BEFORE (12 expected) ===")
    for i, row in enumerate(report["client_gaps_before"], 1):
        cid = row.get("client_id", "")
        print(f"{i}. {row['regulation_code']} pos={row['position_code']} client={cid}")

    print("\n=== ACTIONS ===")
    for a in report["actions"]:
        print("-", a)

    print("\n=== REMAINING GLOBAL gaps ===")
    if report["remaining"]["global"]:
        for row in report["remaining"]["global"]:
            print(row)
    else:
        print("(none)")

    print("\n=== REMAINING CLIENT gaps ===")
    if report["remaining"]["client"]:
        for i, row in enumerate(report["remaining"]["client"], 1):
            print(f"{i}. {row}")
    else:
        print("(none)")


if __name__ == "__main__":
    main()
