"""HR-dosed test release for psychological testing assignments."""

from __future__ import annotations

from tests.conftest import onboarding_payload


def _create_assignment(client, *, suffix: str = "a"):
    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"psych_hr_release_{suffix}",
            client_name=f"Psych HR Release {suffix}",
            admin_login=f"psych_hr_release_admin_{suffix}",
        ),
    )
    assert onboard.status_code == 200
    client_id = onboard.json()["client_id"]
    emp_id = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"][0]["id"]
    created = client.post(
        "/api/psychological-testing/assignments",
        json={"client_id": client_id, "employee_id": emp_id},
    )
    assert created.status_code == 200
    return client_id, emp_id, created.json()


def test_new_assignment_releases_only_first_test(client):
    _client_id, _emp_id, body = _create_assignment(client)
    assert body["released_tests"] == ["mbti"]
    assert body["allowed_test_ids"] == ["mbti"]
    assert body["pending_hr_release_test_ids"] == []


def test_release_endpoint_opens_next_test(client):
    client_id, emp_id, body = _create_assignment(client, suffix="release")
    aid = body["id"]

    from app.db import SessionLocal
    from app.services.psych_test_assignments import record_test_completed

    with SessionLocal() as db:
        record_test_completed(db, client_id=client_id, employee_id=emp_id, test_id="mbti")

    listed = client.get(
        "/api/psychological-testing/assignments",
        params={"client_id": client_id},
    )
    item = next(x for x in listed.json()["items"] if x["id"] == aid)
    assert item["allowed_test_ids"] == []
    assert "soft_skills" in item["pending_hr_release_test_ids"]
    assert item["needs_hr_release"] is True

    released = client.post(
        f"/api/psychological-testing/assignments/{aid}/release",
        json={"notify": False},
    )
    assert released.status_code == 200
    data = released.json()
    assert "soft_skills" in data["released_tests"]
    assert data["allowed_test_ids"] == ["soft_skills"]
    assert data["needs_hr_release"] is False
