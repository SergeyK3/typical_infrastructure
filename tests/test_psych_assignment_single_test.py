"""Назначение одного test_id (без шаблонов программ)."""

from __future__ import annotations

from tests.conftest import onboarding_payload


def _onboard(client, *, suffix: str):
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"psych_single_{suffix}",
            client_name=f"Psych Single {suffix}",
            admin_login=f"psych_single_admin_{suffix}",
        ),
    )
    assert r.status_code == 200
    return r.json()["client_id"]


def test_assignment_create_single_test_and_replace(client):
    client_id = _onboard(client, suffix="one")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]

    created = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "test_id": "mbti",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["test_id"] == "mbti"
    assert body["status"] == "scheduled"
    assert body.get("due_at")

    blocked = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "test_id": "disc",
        },
    )
    assert blocked.status_code == 400
    err = blocked.json().get("error") or {}
    assert "активное назначение" in str(err.get("message", ""))

    created2 = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "test_id": "disc",
            "replace_active": True,
        },
    )
    assert created2.status_code == 200
    assert created2.json()["test_id"] == "disc"

    listed = client.get(
        "/api/psychological-testing/assignments",
        params={"client_id": client_id},
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) >= 2
    by_test = {a["test_id"]: a for a in items}
    assert by_test["mbti"]["status"] == "superseded"
    assert by_test["disc"]["status"] in ("scheduled", "notified", "in_progress")
    active = [a for a in items if a["status"] not in ("completed", "cancelled", "superseded")]
    assert len(active) == 1
    assert active[0]["test_id"] == "disc"


def test_assignment_same_test_is_idempotent(client):
    client_id = _onboard(client, suffix="idem")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]

    first = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id, "test_id": "mbti"},
    ).json()
    second = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id, "test_id": "mbti"},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]


def test_record_completion_by_assignment_id_after_supersede(client):
    from app.db import SessionLocal
    from app.services.psych_test_assignments import (
        create_assignment,
        record_test_completed,
    )

    client_id = _onboard(client, suffix="hist")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]

    with SessionLocal() as db:
        mbti_row = create_assignment(
            db, client_id=client_id, employee_id=emp_id, test_id="mbti"
        )
        mbti_id = mbti_row.id
        create_assignment(
            db, client_id=client_id, employee_id=emp_id, test_id="disc", replace_active=True
        )

        done = record_test_completed(
            db,
            client_id=client_id,
            employee_id=emp_id,
            test_id="mbti",
            assignment_id=mbti_id,
            session_id="sess-history-001",
        )
        assert done is not None
        assert done.status == "completed"
        assert done.session_id == "sess-history-001"
        assert done.completed_at is not None


def test_check_may_start_test_gate(client):
    from app.db import SessionLocal
    from app.services.psych_test_assignments import check_may_start_test, create_assignment

    client_id = _onboard(client, suffix="gate")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]

    with SessionLocal() as db:
        create_assignment(db, client_id=client_id, employee_id=emp_id, test_id="hexaco")
        ok, msg, _ = check_may_start_test(
            db, client_id=client_id, employee_id=emp_id, test_id="mbti"
        )
        assert not ok
        assert msg
        ok2, _, _ = check_may_start_test(
            db, client_id=client_id, employee_id=emp_id, test_id="hexaco"
        )
        assert ok2


def test_notify_superseded_row_requires_new_assignment(client, monkeypatch):
    from psychological_testing.adapters.telegram_outbound import FakeTelegramOutbound

    fake = FakeTelegramOutbound()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PSYCH_TESTING_TELEGRAM_OUTBOUND", "mock")
    monkeypatch.setattr(
        "app.services.psych_test_assignments.get_telegram_outbound",
        lambda: fake,
    )

    client_id = _onboard(client, suffix="notify_recreate")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]
    client.patch(f"/api/employees/{emp_id}", json={"telegram_id": "79990003344"})

    old = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id, "test_id": "mbti"},
    ).json()
    disc = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "test_id": "disc",
            "replace_active": True,
        },
    ).json()
    from app.db import SessionLocal
    from app.services.psych_test_assignments import record_test_completed

    with SessionLocal() as db:
        record_test_completed(
            db,
            client_id=client_id,
            employee_id=emp_id,
            test_id="disc",
            assignment_id=disc["id"],
        )
    listed = client.get(
        "/api/psychological-testing/assignments",
        params={"client_id": client_id},
    ).json()["items"]
    old_row = next(a for a in listed if a["id"] == old["id"])
    assert old_row["status"] == "superseded"

    r = client.post(f"/api/psychological-testing/assignments/{old['id']}/notify")
    assert r.status_code == 400
    err = r.json().get("error") or {}
    assert "активного назначения" in str(err.get("message", ""))
    assert len(fake.messages) == 0


def test_notify_superseded_row_uses_active_assignment(client, monkeypatch):
    from psychological_testing.adapters.telegram_outbound import FakeTelegramOutbound

    fake = FakeTelegramOutbound()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PSYCH_TESTING_TELEGRAM_OUTBOUND", "mock")
    monkeypatch.setattr(
        "app.services.psych_test_assignments.get_telegram_outbound",
        lambda: fake,
    )

    client_id = _onboard(client, suffix="notify_active")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]
    client.patch(f"/api/employees/{emp_id}", json={"telegram_id": "79990001122"})

    old = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id, "test_id": "mbti"},
    ).json()
    new = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "test_id": "paei",
            "replace_active": True,
        },
    ).json()

    r = client.post(f"/api/psychological-testing/assignments/{old['id']}/notify")
    assert r.status_code == 200
    assert r.json()["test_id"] == "paei"
    assert len(fake.messages) == 1
