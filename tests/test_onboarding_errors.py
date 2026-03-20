r"""Error tests: inconsistent references, validation, conflicts."""

from __future__ import annotations

import pytest

from tests.conftest import onboarding_payload


def test_client_code_already_exists(client, valid_payload):
    """Duplicate client code returns 409."""
    payload = onboarding_payload(client_code="dup_client", admin_login="dup_admin_1")
    r1 = client.post("/api/onboarding-runs", json=payload)
    assert r1.status_code == 200

    payload2 = onboarding_payload(client_code="dup_client", admin_login="dup_admin_2")
    r2 = client.post("/api/onboarding-runs", json=payload2)
    assert r2.status_code == 409
    err = r2.json().get("error", {})
    if isinstance(err, dict):
        assert err.get("code") == "client_code_already_exists"


def test_login_already_exists(client, valid_payload):
    """Duplicate admin login returns 409."""
    payload1 = onboarding_payload(client_code="dup_login_1", admin_login="same_login")
    r1 = client.post("/api/onboarding-runs", json=payload1)
    assert r1.status_code == 200

    payload2 = onboarding_payload(client_code="dup_login_2", admin_login="same_login")
    r2 = client.post("/api/onboarding-runs", json=payload2)
    assert r2.status_code == 409
    err = r2.json().get("error", {})
    if isinstance(err, dict):
        assert err.get("code") == "login_already_exists"


def test_template_not_found(client):
    """Invalid template code returns 400."""
    payload = onboarding_payload(template_code="invalid_template_xyz")
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 400
    err = r.json().get("error", {})
    if isinstance(err, dict):
        assert err.get("code") == "template_not_found"


def test_validation_empty_client_code(client):
    """Empty client code returns 422."""
    payload = onboarding_payload(client_code="", client_name="Test")
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 422


def test_validation_missing_client(client):
    """Missing client object returns 422."""
    payload = {
        "template_code": "default",
        "admin": {
            "last_name": "A",
            "first_name": "B",
            "login": "ab",
            "password": "x",
            "email": None,
        },
    }
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 422


def test_validation_extra_fields_rejected(client, valid_payload):
    """Unknown fields in payload are rejected (extra=forbid)."""
    payload = {**valid_payload, "unknown_field": "value"}
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 422


def test_run_not_found(client):
    """GET non-existent run returns 404."""
    r = client.get("/api/onboarding-runs/nonexistent_run_id_xyz")
    assert r.status_code == 404
