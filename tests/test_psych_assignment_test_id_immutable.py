"""test_id назначения неизменяем после создания; PATCH меняет только due_at."""

from __future__ import annotations

from app.db import SessionLocal
from app.models import PtTestAssignment

from tests.conftest import onboarding_payload


def _onboard(client, *, suffix: str):
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"imm_{suffix}",
            client_name=f"Immutable {suffix}",
            admin_login=f"imm_admin_{suffix}",
        ),
    )
    assert r.status_code == 200
    return r.json()["client_id"]


def test_assignment_patch_does_not_change_test_id(client):
    client_id = _onboard(client, suffix="patch")
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]

    created = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id, "test_id": "mbti"},
    )
    assert created.status_code == 200
    body = created.json()
    assignment_id = body["id"]
    assert body["test_id"] == "mbti"

    patched = client.patch(
        f"/api/psychological-testing/assignments/{assignment_id}",
        json={"due_at": "2030-12-31T23:59:59"},
    )
    assert patched.status_code == 200
    assert patched.json()["test_id"] == "mbti"

    with SessionLocal() as db:
        row = db.get(PtTestAssignment, assignment_id)
        assert row is not None
        assert row.test_id == "mbti"


def test_bot_test_id_for_step_uses_single_assignment():
    from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter

    adapter = PsychTestingTelegramAdapter.__new__(PsychTestingTelegramAdapter)
    adapter._assignment_menu_context = lambda _chat: {
        "allowed_test_ids": ["hexaco"],
        "allowed_steps": [],
    }
    test_id, mode = adapter._test_id_for_step("1", "disc")
    assert test_id == "hexaco"
    assert mode is None
