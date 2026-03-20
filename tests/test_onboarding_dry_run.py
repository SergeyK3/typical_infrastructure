r"""Dry-run contract tests for onboarding."""

from __future__ import annotations

import pytest

from tests.conftest import onboarding_payload


def test_dry_run_returns_200(client, valid_payload):
    """Dry-run with valid payload returns 200 and status dry_run."""
    r = client.post("/api/onboarding-runs?dry_run=true", json=valid_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "dry_run"
    assert data["client_id"] is None


def test_dry_run_no_entities_created(client, valid_payload):
    """Dry-run does not create client or other entities."""
    r = client.post("/api/onboarding-runs?dry_run=true", json=valid_payload)
    assert r.status_code == 200
    assert r.json()["status"] == "dry_run"

    # Client should not exist
    r2 = client.get("/api/clients")
    items = r2.json()["items"]
    codes = [c["code"] for c in items]
    assert valid_payload["client"]["code"] not in codes


def test_dry_run_steps_skipped(client, valid_payload):
    """All steps in dry-run are marked skipped."""
    r = client.post("/api/onboarding-runs?dry_run=true", json=valid_payload)
    assert r.status_code == 200
    run_id = r.json()["id"]

    r2 = client.get(f"/api/onboarding-runs/{run_id}")
    assert r2.status_code == 200
    steps = r2.json()["steps"]
    for s in steps:
        assert s["status"] == "skipped"


def test_dry_run_then_real_run(client, valid_payload):
    """Dry-run passes, then real run creates entities."""
    payload = onboarding_payload(client_code="dry_then_real", admin_login="dry_then_real_admin")

    r1 = client.post("/api/onboarding-runs?dry_run=true", json=payload)
    assert r1.status_code == 200
    assert r1.json()["status"] == "dry_run"

    r2 = client.post("/api/onboarding-runs?dry_run=false", json=payload)
    assert r2.status_code == 200
    assert r2.json()["status"] == "completed"
    assert r2.json()["client_id"] is not None


def test_dry_run_template_not_found(client, valid_payload):
    """Dry-run with invalid template returns 400 before creating run."""
    payload = onboarding_payload(template_code="nonexistent_template_xyz")
    r = client.post("/api/onboarding-runs?dry_run=true", json=payload)
    assert r.status_code == 400
    err = r.json().get("error", {})
    if isinstance(err, dict):
        assert err.get("code") == "template_not_found"
