"""Audit: telegram bind-code flow, DB state for target user."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = os.environ.get("SQLITE_PATH") or str(ROOT / "app.db")


def main() -> int:
    print(f"DB path: {DB}")
    if not Path(DB).exists():
        print("ERROR: database file not found")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\n=== Tables ({len(tables)}) ===")
    interesting = [t for t in tables if any(k in t.lower() for k in ("telegram", "bind", "person", "identity", "user"))]
    for t in interesting or ["(none matching telegram/bind/person/identity/user)"]:
        print(f"  {t}")

    has_binding_codes = "telegram_binding_codes" in tables
    print(f"\ntelegram_binding_codes exists: {has_binding_codes}")

    print("\n=== Search employee: 'Амбулаторный эксперт' ===")
    patterns = ["%Амбулаторный эксперт%", "%амбулаторный эксперт%", "%эксперт%"]
    found = []
    for pat in patterns:
        cur.execute(
            """
            SELECT id, client_id, last_name, first_name, middle_name, email, telegram_id
            FROM employees
            WHERE last_name LIKE ? OR first_name LIKE ? OR middle_name LIKE ?
               OR (last_name || ' ' || first_name) LIKE ?
            LIMIT 50
            """,
            (pat, pat, pat, pat),
        )
        for row in cur.fetchall():
            if row["id"] not in {r["id"] for r in found}:
                found.append(dict(row))

    if not found:
        print("  No employees found. Trying accounts.login …")
        cur.execute(
            "SELECT id, login, employee_id, status FROM accounts WHERE login LIKE ? LIMIT 20",
            ("%эксперт%",),
        )
        for row in cur.fetchall():
            print(dict(row))
    else:
        for emp in found:
            print("\n--- Employee ---")
            for k, v in emp.items():
                print(f"  {k}: {v}")
            eid = emp["id"]
            cid = emp["client_id"]

            cur.execute(
                "SELECT a.id AS account_id, a.login, a.status FROM accounts a WHERE a.employee_id = ?",
                (eid,),
            )
            accs = cur.fetchall()
            print("  accounts:", [dict(r) for r in accs])

            if has_binding_codes:
                cur.execute(
                    "SELECT * FROM telegram_binding_codes WHERE employee_id = ? ORDER BY created_at DESC",
                    (eid,),
                )
                print("  telegram_binding_codes:", [dict(r) for r in cur.fetchall()])

            for tbl in ("pt_telegram_bindings", "sa_examination_telegram_bindings"):
                if tbl in tables:
                    cur.execute(f"SELECT * FROM {tbl} WHERE employee_id = ?", (eid,))
                    print(f"  {tbl}:", [dict(r) for r in cur.fetchall()])

            if "persons" in tables:
                cur.execute("SELECT * FROM persons WHERE employee_id = ?", (eid,))
                print("  persons:", [dict(r) for r in cur.fetchall()])

    cur.execute("SELECT id, client_id, last_name, first_name, middle_name, email, telegram_id FROM employees")
    all_employees = [dict(r) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT id, client_id, code, name FROM positions
        WHERE lower(name) LIKE '%амбул%' OR lower(code) LIKE '%ambul%'
        LIMIT 20
        """
    )
    positions_ambul = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT id, login, employee_id, status FROM accounts")
    accounts = [dict(r) for r in cur.fetchall()]

    bindings = {}
    for tbl in ("pt_telegram_bindings", "sa_examination_telegram_bindings"):
        if tbl in tables:
            cur.execute(f"SELECT * FROM {tbl}")
            bindings[tbl] = [dict(r) for r in cur.fetchall()]

    import json

    report = {
        "db_path": DB,
        "tables_interesting": interesting,
        "has_telegram_binding_codes": has_binding_codes,
        "total_employees": len(all_employees),
        "employee_matches": found,
        "positions_ambul": positions_ambul,
        "accounts": accounts,
        "bindings": bindings,
    }
    out_path = ROOT / "scripts" / "_audit_bind_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report written: {out_path}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
