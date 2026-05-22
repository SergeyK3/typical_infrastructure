"""Manager RBAC: view_team scope (same org_unit), no assign/export."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, AccountRole, Employee, OrgUnit, Role
from app.utils import new_id32
from tests.conftest import onboarding_payload


def _assign_role(db, account_id: str, role_code: str) -> None:
    role = db.scalar(select(Role).where(Role.code == role_code, Role.is_active == True))  # noqa: E712
    assert role is not None
    db.add(
        AccountRole(
            id=new_id32(),
            account_id=account_id,
            role_id=role.id,
        )
    )
    db.commit()


def _setup_manager_team(client, monkeypatch: pytest.MonkeyPatch, *, suffix: str = "a"):
    monkeypatch.setenv("PSYCH_TESTING_RBAC_VIEW", "1")
    monkeypatch.setenv("PSYCH_TESTING_RBAC_ASSIGN", "1")
    monkeypatch.setenv("PSYCH_TESTING_RBAC_EXPORT", "1")
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"psych_mgr_{suffix}",
            client_name=f"Psych Manager RBAC {suffix}",
            admin_login=f"psych_mgr_admin_{suffix}",
        ),
    )
    assert onboard.status_code == 200
    client_id = onboard.json()["client_id"]
    admin_account_id = onboard.json()["created_entities"]["account_id"]

    with SessionLocal() as db:
        ou = OrgUnit(
            id=new_id32(),
            client_id=client_id,
            code="SALES",
            name="Sales",
            parent_id=None,
            unit_type="dept",
        )
        db.add(ou)
        db.flush()

        mgr_emp = Employee(
            id=new_id32(),
            client_id=client_id,
            last_name="Manager",
            first_name="Team",
            employment_status="active",
            org_unit_id=ou.id,
            is_manager=True,
        )
        rep1 = Employee(
            id=new_id32(),
            client_id=client_id,
            last_name="Report",
            first_name="One",
            employment_status="active",
            org_unit_id=ou.id,
        )
        rep2 = Employee(
            id=new_id32(),
            client_id=client_id,
            last_name="Report",
            first_name="Two",
            employment_status="active",
            org_unit_id=ou.id,
        )
        outsider = Employee(
            id=new_id32(),
            client_id=client_id,
            last_name="Other",
            first_name="Dept",
            employment_status="active",
            org_unit_id=None,
        )
        db.add_all([mgr_emp, rep1, rep2, outsider])

        mgr_acc = Account(
            id=new_id32(),
            employee_id=mgr_emp.id,
            login="psych_mgr_team_lead",
            password_hash="x",
            status="active",
        )
        db.add(mgr_acc)
        db.flush()
        _assign_role(db, mgr_acc.id, "manager")

        for emp_id, test_id, sid in (
            (rep1.id, "disc", "sess-mgr-rep1"),
            (rep2.id, "hexaco", "sess-mgr-rep2"),
            (outsider.id, "paei", "sess-mgr-out"),
        ):
            from psychological_testing.integration.session_persistence import sessions_dir

            day_dir = sessions_dir() / "2026-05-22"
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / f"{sid}.json").write_text(
                json.dumps(
                    {
                        "session_id": sid,
                        "client_id": client_id,
                        "employee_id": emp_id,
                        "employee_display_name": emp_id[:8],
                        "test_id": test_id,
                        "status": "done",
                        "completed_at": "2026-05-22T12:00:00+00:00",
                        "scores": {"typology_code": "X"},
                        "report": {"text_telegram": "ok"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        db.commit()
        return client_id, admin_account_id, mgr_acc.id, rep1.id, rep2.id, outsider.id


def test_manager_sees_team_sessions_only(client, monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path / "sessions"))
    client_id, _admin, mgr_acc, rep1, _rep2, outsider = _setup_manager_team(
        client, monkeypatch, suffix="team"
    )

    mgr_list = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id, "account_id": mgr_acc, "limit": 50},
    )
    assert mgr_list.status_code == 200
    ids = {x["session_id"] for x in mgr_list.json()["items"]}
    assert "sess-mgr-rep1" in ids
    assert "sess-mgr-rep2" in ids
    assert "sess-mgr-out" not in ids

    denied = client.get(
        f"/api/psychological-testing/sessions/sess-mgr-out",
        params={"client_id": client_id, "account_id": mgr_acc},
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/api/psychological-testing/sessions/sess-mgr-rep1",
        params={"client_id": client_id, "account_id": mgr_acc},
    )
    assert allowed.status_code == 200


def test_manager_cannot_assign_or_export(client, monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path / "sessions"))
    client_id, _admin, mgr_acc, rep1, _rep2, _outsider = _setup_manager_team(
        client, monkeypatch, suffix="deny"
    )

    created = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": rep1,
            "test_id": "mbti",
            "account_id": mgr_acc,
        },
    )
    assert created.status_code == 403

    preview = client.get(
        f"/api/psychological-testing/employees/{rep1}/export-preview",
        params={"client_id": client_id, "account_id": mgr_acc},
    )
    assert preview.status_code == 403


def test_rbac_context_permissions(client, monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path / "sessions"))
    client_id, admin_acc, mgr_acc, _rep1, _rep2, _outsider = _setup_manager_team(
        client, monkeypatch, suffix="ctx"
    )

    ctx = client.get(
        "/api/psychological-testing/rbac-context",
        params={"client_id": client_id},
    )
    assert ctx.status_code == 200
    data = ctx.json()
    assert data["workspace_account_id"] == admin_acc
    assert data["can_assign"] is True
    assert data["can_export"] is True
    assert data["scope"] == "all_org"

    from app.services.psych_rbac import permissions_for_account

    with SessionLocal() as db:
        mgr_perms = permissions_for_account(db, account_id=mgr_acc, client_id=client_id)
    assert mgr_perms["scope"] == "team"
    assert mgr_perms["can_view"] is True
    assert mgr_perms["can_assign"] is False
    assert mgr_perms["can_export"] is False
