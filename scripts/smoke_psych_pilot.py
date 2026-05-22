#!/usr/bin/env python3
"""Smoke: RBAC + Drive + persist_db with live .env and app.db."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Client
from app.services.psych_rbac import resolve_hr_admin_account_id
from fastapi.testclient import TestClient
from psychological_testing.integration.report_storage import is_gdrive_ref
from psychological_testing.integration.session_repository import list_session_summaries


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    client = TestClient(app)
    print("=== psych pilot smoke (.env + app.db) ===")

    st = client.get("/api/psychological-testing/status")
    if st.status_code != 200:
        _fail(f"status HTTP {st.status_code}")
    data = st.json()
    print(
        "status:",
        f"json={data['persist_json_enabled']}",
        f"db={data['persist_db_enabled']}",
        f"gdrive={data['gdrive_configured']}",
        f"rbac assign/view/export="
        f"{data['rbac_assign_enforced']}/{data['rbac_view_enforced']}/{data['rbac_export_enforced']}",
    )
    if not data["persist_db_enabled"]:
        _fail("persist_db_enabled is false")
    if not data["gdrive_configured"]:
        _fail("gdrive_configured is false")
    if not (data["rbac_assign_enforced"] and data["rbac_view_enforced"] and data["rbac_export_enforced"]):
        _fail("RBAC flags not all enabled")

    db = SessionLocal()
    try:
        org = None
        emp_id = None
        for c in db.scalars(select(Client).order_by(Client.created_at.desc()).limit(20)).all():
            items, total = list_session_summaries(client_id=c.id, limit=1)
            if total and items:
                org = c
                emp_id = items[0].get("employee_id")
                break
        if not org or not emp_id:
            _fail("no completed psych sessions in app.db — run a Telegram test first")
        client_id = org.id
        account_id = resolve_hr_admin_account_id(db, client_id)
        if not account_id:
            _fail(f"no hr_admin account for client {client_id}")
    finally:
        db.close()

    print(f"org: {org.name!r} client_id={client_id[:8]}… emp={emp_id[:8]}… account={account_id[:8]}…")

    ctx = client.get(
        "/api/psychological-testing/rbac-context",
        params={"client_id": client_id},
    )
    if ctx.status_code != 200 or ctx.json().get("hr_admin_account_id") != account_id:
        _fail("rbac-context mismatch")
    print("OK   rbac-context")

    denied = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id, "limit": 5},
    )
    if denied.status_code != 403:
        _fail(f"sessions without account_id expected 403, got {denied.status_code}")
    print("OK   sessions denied without account_id")

    allowed = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id, "account_id": account_id, "limit": 5},
    )
    if allowed.status_code != 200 or not allowed.json().get("items"):
        _fail(f"sessions with account_id failed: {allowed.status_code}")
    print(f"OK   sessions list ({allowed.json()['total']} total)")

    preview = client.get(
        f"/api/psychological-testing/employees/{emp_id}/export-preview",
        params={"client_id": client_id, "account_id": account_id},
    )
    if preview.status_code != 200:
        _fail(f"export-preview HTTP {preview.status_code}: {preview.text[:200]}")
    sections = [
        {"section_id": s["section_id"], "enabled": bool(s.get("enabled", True))}
        for s in preview.json().get("manifest", {}).get("sections", [])
        if s.get("enabled", True)
    ][:6]
    print(f"OK   export-preview ({len(sections)} sections)")

    export = client.post(
        f"/api/psychological-testing/employees/{emp_id}/export-pdf",
        json={
            "client_id": client_id,
            "account_id": account_id,
            "sections": sections,
            "regenerate_ai": False,
            "force_regenerate": False,
            "response_mode": "json",
        },
    )
    if export.status_code != 200:
        _fail(f"export-pdf HTTP {export.status_code}: {export.text[:300]}")
    meta = export.json()
    pdf_ref = meta.get("pdf_ref") or ""
    print(
        "OK   export-pdf",
        f"storage={meta.get('storage_kind')}",
        f"ref={pdf_ref[:40]}…" if pdf_ref else "ref=empty",
        f"bytes={meta.get('size_bytes')}",
    )
    if not is_gdrive_ref(pdf_ref):
        _fail(f"expected gdrive pdf_ref, got {pdf_ref!r}")

    denied_export = client.post(
        f"/api/psychological-testing/employees/{emp_id}/export-pdf",
        json={
            "client_id": client_id,
            "sections": sections[:2],
            "response_mode": "json",
        },
    )
    if denied_export.status_code != 403:
        _fail(f"export without account_id expected 403, got {denied_export.status_code}")
    print("OK   export denied without account_id")

    print("\nAll psych pilot smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
