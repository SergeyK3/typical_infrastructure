r"""Idempotency tests for onboarding."""

from __future__ import annotations

import pytest

from tests.conftest import onboarding_payload


def test_same_key_same_payload_returns_existing(client, idempotency_key):
    """Same idempotency key + same payload returns existing run (200)."""
    payload = onboarding_payload(
        client_code="idem_same",
        admin_login="idem_same_admin",
        idempotency_key=idempotency_key,
    )

    r1 = client.post("/api/onboarding-runs", json=payload, headers={"Idempotency-Key": idempotency_key})
    assert r1.status_code == 200
    run_id_1 = r1.json()["id"]

    r2 = client.post("/api/onboarding-runs", json=payload, headers={"Idempotency-Key": idempotency_key})
    assert r2.status_code == 200
    run_id_2 = r2.json()["id"]
    assert run_id_1 == run_id_2


def test_same_key_different_payload_returns_409(client):
    """Same idempotency key + different payload returns 409 Conflict."""
    key = "idem-diff-key-unique"
    payload1 = onboarding_payload(
        client_code="idem_diff_a",
        admin_login="idem_diff_a_admin",
        idempotency_key=key,
    )
    payload2 = onboarding_payload(
        client_code="idem_diff_b",
        admin_login="idem_diff_b_admin",
        idempotency_key=key,
    )

    r1 = client.post("/api/onboarding-runs", json=payload1, headers={"Idempotency-Key": key})
    assert r1.status_code == 200

    r2 = client.post("/api/onboarding-runs", json=payload2, headers={"Idempotency-Key": key})
    assert r2.status_code == 409
    err = r2.json().get("error", {})
    if isinstance(err, dict):
        assert err.get("code") == "idempotency_key_conflict"
        assert "existing_run_id" in err


def test_idempotency_key_in_body(client):
    """Idempotency key in body is accepted."""
    payload = onboarding_payload(
        client_code="idem_body",
        admin_login="idem_body_admin",
        idempotency_key="body-key-001",
    )
    r1 = client.post("/api/onboarding-runs", json=payload)
    assert r1.status_code == 200

    r2 = client.post("/api/onboarding-runs", json=payload)
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_header_overrides_body_key(client):
    """Idempotency-Key header overrides body key."""
    payload = onboarding_payload(
        client_code="idem_header",
        admin_login="idem_header_admin",
        idempotency_key="body-key-ignored",
    )
    r = client.post(
        "/api/onboarding-runs",
        json=payload,
        headers={"Idempotency-Key": "header-key-wins"},
    )
    assert r.status_code == 200
    # Same header key + same payload should return same run
    r2 = client.post(
        "/api/onboarding-runs",
        json=payload,
        headers={"Idempotency-Key": "header-key-wins"},
    )
    assert r2.status_code == 200
    assert r.json()["id"] == r2.json()["id"]
