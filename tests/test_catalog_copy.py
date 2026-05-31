"""Tests for catalog copy API."""

from __future__ import annotations


def test_copy_template_org_unit_global_to_global(client):
    tpls = client.get("/api/enterprise-templates").json()
    target = next((t["code"] for t in tpls if t["code"] != "default"), None)
    if not target:
        return
    units = client.get("/api/template-org-units?template_code=default&limit=50").json()
    items = units.get("items") or []
    dept = next((u for u in items if u.get("unit_type") == "department" and u.get("code") != "company"), None)
    if not dept:
        return
    new_code = dept["code"] + "_COPYTEST"
    r = client.post(
        "/api/catalog-copy/org-unit",
        json={
            "mode": "global_to_global",
            "source_template_code": "default",
            "target_template_code": target,
            "source_org_unit_id": dept["id"],
            "target_code": new_code,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["row"]["code"] == new_code


def test_copy_kpi_global_to_global(client):
    tpls = client.get("/api/enterprise-templates").json()
    target = next((t["code"] for t in tpls if t["code"] != "default"), None)
    if not target:
        return
    kpis = client.get("/api/kpi-templates?template_code=default&limit=20").json()
    items = kpis.get("items") or []
    if not items:
        return
    code = items[0]["kpi_code"]
    new_code = code + "_COPYTEST"
    r = client.post(
        "/api/catalog-copy/kpi",
        json={
            "mode": "global_to_global",
            "source_template_code": "default",
            "target_template_code": target,
            "source_kpi_code": code,
            "target_kpi_code": new_code,
        },
    )
    if r.status_code == 400 and "position_not_in_target_template" in r.text:
        return
    assert r.status_code == 201, r.text
    assert r.json()["kpi_code"] == new_code
