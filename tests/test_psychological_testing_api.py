"""API for psychological testing session list (workspace)."""

from __future__ import annotations

import json

from tests.conftest import onboarding_payload


def test_psych_testing_status_lists_plugins(client):
    r = client.get("/api/psychological-testing/status")
    assert r.status_code == 200
    data = r.json()
    assert data["persist_json_enabled"] in (True, False)
    assert data["available_tests"]
    assert any("/start " in cmd for cmd in data["telegram_commands"])


def test_psych_sessions_unknown_client_404(client):
    r = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": "00000000000000000000000000000000"},
    )
    assert r.status_code == 404


def test_psych_sessions_filter_by_client(client, tmp_path, monkeypatch):
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")
    sessions_root = tmp_path / "sessions" / "v1"
    day_dir = sessions_root / "2026-05-20"
    day_dir.mkdir(parents=True)
    session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    (day_dir / f"{session_id}.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "client_id": "client_for_psych_api_test",
                "employee_display_name": "Test User",
                "test_id": "disc",
                "status": "done",
                "completed_at": "2026-05-20T10:00:00+00:00",
                "scores": {"typology_code": "DI"},
                "report": {"text_telegram": "Sample report"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(sessions_root))

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_api_org",
            client_name="Psych API Org",
            admin_login="psych_api_admin",
        ),
    )
    assert onboard.status_code == 200
    client_id = onboard.json()["client_id"]

    listed = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    (day_dir / f"{session_id}.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "client_id": client_id,
                "employee_display_name": "Test User",
                "test_id": "disc",
                "status": "done",
                "completed_at": "2026-05-20T10:00:00+00:00",
                "scores": {"typology_code": "DI"},
                "report": {"text_telegram": "Sample report"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    listed2 = client.get(
        "/api/psychological-testing/sessions",
        params={"client_id": client_id},
    )
    assert listed2.status_code == 200
    items = listed2.json()["items"]
    assert len(items) == 1
    assert items[0]["session_id"] == session_id
    assert items[0]["typology_code"] == "DI"

    detail = client.get(f"/api/psychological-testing/sessions/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["client_id"] == client_id


def test_psych_assignment_create_and_programs(client):
    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_assign_org",
            client_name="Psych Assign Org",
            admin_login="psych_assign_admin",
        ),
    )
    assert onboard.status_code == 200
    client_id = onboard.json()["client_id"]
    employees = client.get(f"/api/employees?client_id={client_id}&limit=10").json()["items"]
    assert employees
    emp_id = employees[0]["id"]

    progs = client.get("/api/psychological-testing/programs")
    assert progs.status_code == 200
    assert any(p["program_id"] == "standard_hr_v1" for p in progs.json()["items"])

    created = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "program_id": "standard_hr_v1",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["program_id"] == "standard_hr_v1"
    assert body["next_test_id"] == "mbti"
    assert body["status"] == "scheduled"

    listed = client.get(
        "/api/psychological-testing/assignments",
        params={"client_id": client_id},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    dup = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id},
    )
    assert dup.status_code == 400
    assert body.get("due_at")
    assert body.get("due_date")


def test_psych_assignment_list_backfills_missing_due_at(client, monkeypatch):
    from app.db import SessionLocal
    from app.models import PtTestAssignment

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_due_backfill",
            client_name="Psych Due Backfill",
            admin_login="psych_due_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]

    with SessionLocal() as db:
        row = PtTestAssignment(
            id="legacyassign000000000000000001",
            client_id=client_id,
            employee_id=emp_id,
            program_id="standard_hr_v1",
            status="scheduled",
            completed_tests_json="[]",
            due_at=None,
        )
        db.add(row)
        db.commit()

    listed = client.get(
        "/api/psychological-testing/assignments",
        params={"client_id": client_id},
    )
    assert listed.status_code == 200
    item = next(x for x in listed.json()["items"] if x["id"] == "legacyassign000000000000000001")
    assert item["due_date"]
    assert item["due_at"]


def test_psych_assignment_notify_mock_telegram(client, monkeypatch):
    from psychological_testing.adapters.telegram_outbound import FakeTelegramOutbound

    fake = FakeTelegramOutbound()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-for-notify")
    monkeypatch.setenv("PSYCH_TESTING_TELEGRAM_OUTBOUND", "mock")
    monkeypatch.setattr(
        "app.services.psych_test_assignments.get_telegram_outbound",
        lambda: fake,
    )

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_notify_org",
            client_name="Psych Notify Org",
            admin_login="psych_notify_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]
    client.patch(
        f"/api/employees/{emp_id}",
        json={"telegram_id": "7826888928"},
    )

    created = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id},
    )
    assert created.status_code == 200
    aid = created.json()["id"]

    notified = client.post(f"/api/psychological-testing/assignments/{aid}/notify")
    assert notified.status_code == 200
    assert notified.json()["status"] == "notified"
    assert len(fake.messages) == 1
    assert fake.messages[0]["chat_id"] == "7826888928"


def test_psych_notify_chat_not_found_message(client, monkeypatch):
    from psychological_testing.adapters.telegram_outbound import TelegramOutboundResult

    class FailingOutbound:
        def send_message(self, **kwargs):
            return TelegramOutboundResult(
                ok=False, http_status=400, description="Bad Request: chat not found"
            )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(
        "app.services.psych_test_assignments.get_telegram_outbound",
        lambda: FailingOutbound(),
    )

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_chat_nf",
            client_name="Psych Chat NF",
            admin_login="psych_chat_nf_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = onboard.json()["created_entities"]["employee_id"]
    client.patch(f"/api/employees/{emp_id}", json={"telegram_id": "999888777"})
    created = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id},
    )
    aid = created.json()["id"]
    r = client.post(f"/api/psychological-testing/assignments/{aid}/notify")
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "telegram_chat_not_found"
    assert err.get("stored_telegram_id") == "999888777"
