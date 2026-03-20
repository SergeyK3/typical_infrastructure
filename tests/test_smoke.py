r"""Smoke tests by phases — basic API availability."""

from __future__ import annotations

import pytest


class TestPhase1Foundation:
    """Phase 1: Foundation & Master Data."""

    def test_clients_list(self, client):
        r = client.get("/api/clients")
        assert r.status_code == 200
        assert "items" in r.json()
        assert "total" in r.json()

    def test_enterprise_templates_list(self, client):
        r = client.get("/api/enterprise-templates")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_enterprise_template_detail(self, client):
        r = client.get("/api/enterprise-templates")
        assert r.status_code == 200
        templates = r.json()
        if templates:
            tid = templates[0]["id"]
            r2 = client.get(f"/api/enterprise-templates/{tid}")
            assert r2.status_code == 200
            assert r2.json()["code"] == templates[0]["code"]

    def test_structure_preview(self, client):
        r = client.get("/api/enterprise-templates/default/structure-preview")
        assert r.status_code == 200
        data = r.json()
        assert "org_units" in data
        assert "positions" in data


class TestPhase2OrgCore:
    """Phase 2: Org Structure & Workforce."""

    def test_org_units_requires_client_id(self, client):
        r = client.get("/api/org-units")
        assert r.status_code == 422  # client_id required

    def test_positions_requires_client_id(self, client):
        r = client.get("/api/positions")
        assert r.status_code == 422

    def test_employees_list(self, client):
        r = client.get("/api/employees?client_id=nonexistent")
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestPhase3Accounts:
    """Phase 3: Accounts."""

    def test_accounts_list(self, client):
        r = client.get("/api/accounts?client_id=nonexistent")
        assert r.status_code == 200
        assert "items" in r.json()


class TestStep7Health:
    """Step 7: Production readiness."""

    def test_health_ready(self, client):
        """Health readiness endpoint returns 200."""
        r = client.get("/health/ready")
        assert r.status_code == 200
        assert r.json().get("status") == "ready"

    def test_request_id_in_response(self, client):
        """Response includes X-Request-Id and X-Trace-Id headers."""
        r = client.get("/health/ready")
        assert "X-Request-Id" in r.headers
        assert "X-Trace-Id" in r.headers


class TestPhase4Onboarding:
    """Phase 4: Onboarding orchestration."""

    def test_onboarding_runs_list(self, client):
        r = client.get("/api/onboarding-runs")
        assert r.status_code == 200
        assert "items" in r.json()
