#!/usr/bin/env python3
"""Smoke: RBAC + Drive + persist_db — local (.env + app.db) or remote (--url)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class HttpClient(Protocol):
    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any: ...
    def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any: ...


class _Response:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self._json: Any | None = None

    def json(self) -> Any:
        if self._json is None:
            self._json = json.loads(self.text) if self.text else {}
        return self._json


class RemoteClient:
    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        import httpx

        self._base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> _Response:
        url = f"{self._base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        r = self._client.get(url, headers={"Accept": "application/json"})
        return _Response(r.status_code, r.text)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> _Response:
        r = self._client.post(
            f"{self._base}{path}",
            json=json or {},
            headers={"Accept": "application/json"},
        )
        return _Response(r.status_code, r.text)


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _check_status(data: dict[str, Any]) -> None:
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


def _discover_ids_local() -> tuple[str, str, str, str]:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Client
    from app.services.psych_rbac import resolve_hr_admin_account_id
    from psychological_testing.integration.session_repository import list_session_summaries

    db = SessionLocal()
    try:
        for c in db.scalars(select(Client).order_by(Client.created_at.desc()).limit(20)).all():
            items, total = list_session_summaries(client_id=c.id, limit=1)
            if total and items:
                emp_id = items[0].get("employee_id")
                if not emp_id:
                    continue
                account_id = resolve_hr_admin_account_id(db, c.id)
                if account_id:
                    return c.name or c.id, c.id, emp_id, account_id
        _fail("no completed psych sessions in app.db — run a Telegram test first")
    finally:
        db.close()
    raise AssertionError("unreachable")


def _discover_client_id_remote(client: HttpClient) -> str:
    r = client.get("/api/clients")
    if r.status_code != 200:
        _fail(f"/api/clients HTTP {r.status_code}")
    payload = r.json()
    items = payload.get("items") if isinstance(payload, dict) else payload
    if isinstance(items, list) and items:
        cid = items[0].get("id")
        if cid:
            return str(cid)
    _fail("no clients on remote — seed app.db first")
    raise AssertionError("unreachable")


def _run_rbac_smoke(
    client: HttpClient,
    *,
    client_id: str,
    account_id: str | None,
    emp_id: str | None,
    status_only: bool,
) -> None:
    if account_id:
        ctx = client.get(
            "/api/psychological-testing/rbac-context",
            params={"client_id": client_id},
        )
        if ctx.status_code != 200:
            _fail(f"rbac-context HTTP {ctx.status_code}")
        if ctx.json().get("hr_admin_account_id") != account_id:
            _fail("rbac-context hr_admin_account_id mismatch")
        print("OK   rbac-context")

    denied = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id, "limit": 5},
    )
    if denied.status_code != 403:
        _fail(f"sessions without account_id expected 403, got {denied.status_code}")
    print("OK   sessions denied without account_id")

    if status_only or not account_id:
        print("\nStatus-only psych smoke checks passed.")
        return

    allowed = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id, "account_id": account_id, "limit": 5},
    )
    if allowed.status_code != 200 or not allowed.json().get("items"):
        _fail(f"sessions with account_id failed: {allowed.status_code}")
    print(f"OK   sessions list ({allowed.json()['total']} total)")

    if not emp_id:
        _fail("--employee-id required for export smoke (or run locally without --url)")
    assert emp_id is not None

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

    from psychological_testing.integration.report_storage import is_gdrive_ref

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Psych pilot smoke (RBAC + Drive + export)")
    parser.add_argument(
        "--url",
        help="Remote base URL (e.g. https://prod.example.com). Omit for local TestClient + app.db.",
    )
    parser.add_argument("--client-id", help="Client UUID (required for remote full smoke)")
    parser.add_argument("--account-id", help="HR admin account UUID (required for remote full smoke)")
    parser.add_argument("--employee-id", help="Employee UUID for export smoke")
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only /status + RBAC denial checks (no export, no app.db)",
    )
    args = parser.parse_args()

    if args.url:
        client: HttpClient = RemoteClient(args.url)
        label = f"remote {args.url.rstrip('/')}"
    else:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        label = "local .env + app.db"

    print(f"=== psych pilot smoke ({label}) ===")

    st = client.get("/api/psychological-testing/status")
    if st.status_code != 200:
        _fail(f"status HTTP {st.status_code}")
    _check_status(st.json())

    client_id = args.client_id
    account_id = args.account_id
    emp_id = args.employee_id
    org_name = ""

    if not client_id:
        if args.url:
            client_id = _discover_client_id_remote(client)
            print(f"client_id (from /api/clients): {client_id[:8]}…")
        else:
            org_name, client_id, emp_id, account_id = _discover_ids_local()
            print(
                f"org: {org_name!r} client_id={client_id[:8]}… "
                f"emp={emp_id[:8]}… account={account_id[:8]}…"
            )

    status_only = args.status_only or (args.url and not args.account_id)
    if args.url and args.account_id and not args.employee_id and not args.status_only:
        _fail("remote full smoke requires --employee-id when --account-id is set")

    _run_rbac_smoke(
        client,
        client_id=client_id,
        account_id=account_id if not status_only else None,
        emp_id=emp_id,
        status_only=status_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
