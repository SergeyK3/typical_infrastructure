"""effective_log_group в ответах /api/org-units."""

from __future__ import annotations

from tests.conftest import onboarding_payload


def _onboard(client, *, suffix: str):
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"loggrp_{suffix}",
            client_name=f"LogGroup {suffix}",
            admin_login=f"loggrp_admin_{suffix}",
        ),
    )
    assert r.status_code == 200
    return r.json()["client_id"]


def test_org_units_tree_includes_effective_log_group(client):
    client_id = _onboard(client, suffix="tree")
    tree = client.get("/api/org-units/tree", params={"client_id": client_id}).json()

    def flatten(nodes, out=None):
        out = out or []
        for n in nodes or []:
            out.append(n)
            flatten(n.get("children") or [], out)
        return out

    units = flatten(tree)
    departments = [u for u in units if u.get("unit_type") == "department"]
    assert departments, "expected departments from onboarding template"
    for dept in departments:
        assert "effective_log_group" in dept
