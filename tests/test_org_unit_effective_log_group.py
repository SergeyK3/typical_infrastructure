"""effective_log_group и effective_log_group_name в ответах /api/org-units."""

from __future__ import annotations

from app.db import SessionLocal
from app.medical_org_groups import (
    LOG_GROUP_ADMIN_HOUSEHOLD,
    LOG_GROUP_CLINICAL,
    LOG_GROUP_PARACLINICAL,
)
from app.medical_template_excel import load_medical_org_excel
from scripts.backfill_medical_org_unit_groups import backfill_client_org_units
from tests.conftest import onboarding_payload


def _onboard(client, *, suffix: str, template_code: str = "default"):
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"loggrp_{suffix}",
            client_name=f"LogGroup {suffix}",
            admin_login=f"loggrp_admin_{suffix}",
            template_code=template_code,
        ),
    )
    assert r.status_code == 200
    return r.json()["client_id"]


def _flatten_tree(nodes, out=None):
    out = out or []
    for n in nodes or []:
        out.append(n)
        _flatten_tree(n.get("children") or [], out)
    return out


def test_org_units_tree_includes_effective_log_group(client):
    client_id = _onboard(client, suffix="tree")
    tree = client.get("/api/org-units/tree", params={"client_id": client_id}).json()

    units = _flatten_tree(tree)
    departments = [u for u in units if u.get("unit_type") == "department"]
    assert departments, "expected departments from onboarding template"
    for dept in departments:
        assert "effective_log_group" in dept
        assert "effective_log_group_name" in dept


def test_org_units_tree_medical_log_group_names(client):
    client_id = _onboard(client, suffix="medical", template_code="medical")
    excel = load_medical_org_excel()
    db = SessionLocal()
    try:
        backfill_client_org_units(db, client_id, excel, apply=True)
    finally:
        db.close()

    tree = client.get("/api/org-units/tree", params={"client_id": client_id}).json()
    units = _flatten_tree(tree)
    by_code = {u["code"]: u for u in units if u.get("code")}

    poly = by_code["POLYCLINNC"]
    assert poly.get("effective_log_group") == LOG_GROUP_CLINICAL
    assert poly.get("effective_log_group_name") == "Клинические"

    oper = by_code["OPER"]
    assert oper.get("effective_log_group") == LOG_GROUP_PARACLINICAL
    assert oper.get("effective_log_group_name") == "Параклинические"

    admin = by_code["ADM"]
    assert admin.get("effective_log_group") == LOG_GROUP_ADMIN_HOUSEHOLD
    assert admin.get("effective_log_group_name") == "Административно-хозяйственные"
