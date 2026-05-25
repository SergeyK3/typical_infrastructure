r"""Тесты клонирования и каскадного удаления подразделений."""

from __future__ import annotations

import uuid

from tests.conftest import onboarding_payload


def _error_payload(r):
    data = r.json()
    if "error" in data:
        return data["error"]
    detail = data.get("detail")
    if isinstance(detail, dict):
        return detail
    return {"code": detail, "message": str(detail)}


def _error_code(r):
    return _error_payload(r).get("code")


def _find_unit(tree, code: str):
    for n in tree:
        if n.get("code") == code:
            return n
        found = _find_unit(n.get("children") or [], code)
        if found:
            return found
    return None


def _setup_client(client):
    suffix = uuid.uuid4().hex[:8]
    code = f"ou_clone_{suffix}"
    login = f"ou_clone_{suffix}@test.example"
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(client_code=code, client_name=code, admin_login=login),
    )
    assert r.status_code in (200, 201), r.text
    cid = r.json()["client_id"]
    tree = client.get("/api/org-units/tree", params={"client_id": cid}).json()
    return cid, tree


def test_clone_local_department_with_positions(client):
    cid, tree = _setup_client(client)
    hr = _find_unit(tree, "HR")
    assert hr

    positions_before = client.get("/api/positions", params={"client_id": cid}).json()["items"]
    hr_positions = [p for p in positions_before if p["org_unit_id"] == hr["id"]]

    r = client.post(f"/api/org-units/{hr['id']}/clone", json={"name_suffix": "Копия"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["sections_skipped"] >= 0
    assert data["org_unit"]["code"].startswith("HR_COPY")
    assert "Копия" in data["org_unit"]["name"]
    assert data["positions_created"] == len(hr_positions)

    tree2 = client.get("/api/org-units/tree", params={"client_id": cid}).json()
    copy_node = next(
        (c for c in (_find_unit(tree2, "company") or {}).get("children", []) if c["id"] == data["org_unit"]["id"]),
        None,
    )
    assert copy_node is not None
    assert not copy_node.get("children")


def test_clone_does_not_copy_sections(client):
    cid, tree = _setup_client(client)
    hr = _find_unit(tree, "HR")
    assert hr and hr.get("children")

    r = client.post(f"/api/org-units/{hr['id']}/clone", json={})
    assert r.status_code == 201, r.text
    assert r.json()["sections_skipped"] == len(hr["children"])

    tree2 = client.get("/api/org-units/tree", params={"client_id": cid}).json()
    copy = _find_unit(tree2, r.json()["org_unit"]["code"])
    assert copy
    assert copy.get("children") in (None, [])


def test_clone_with_employees_on_position_unchanged(client):
    cid, tree = _setup_client(client)
    adm = _find_unit(tree, "ADM")
    assert adm

    positions = client.get("/api/positions", params={"client_id": cid}).json()["items"]
    pos = next((p for p in positions if p["org_unit_id"] == adm["id"]), None)
    if not pos:
        return

    emp_r = client.post(
        "/api/employees",
        json={
            "client_id": cid,
            "last_name": "Test",
            "first_name": "Emp",
            "org_unit_id": adm["id"],
            "position_id": pos["id"],
            "employment_status": "active",
        },
    )
    assert emp_r.status_code in (200, 201), emp_r.text
    emp_id = emp_r.json()["id"]

    clone_r = client.post(f"/api/org-units/{adm['id']}/clone", json={})
    assert clone_r.status_code == 201, clone_r.text

    emp = client.get("/api/employees", params={"client_id": cid, "limit": 50}).json()
    emp_row = next(e for e in emp["items"] if e["id"] == emp_id)
    assert emp_row["org_unit_id"] == adm["id"]


def test_delete_department_leaf_has_children(client):
    cid, tree = _setup_client(client)
    hr = _find_unit(tree, "HR")
    assert hr and hr.get("children")

    r = client.delete(f"/api/org-units/{hr['id']}")
    assert r.status_code == 400
    assert _error_code(r) == "org_unit_has_children"


def test_delete_department_cascade(client):
    cid, tree = _setup_client(client)
    hr = _find_unit(tree, "HR")
    assert hr

    r = client.delete(f"/api/org-units/{hr['id']}?mode=cascade")
    assert r.status_code == 204, r.text

    tree2 = client.get("/api/org-units/tree", params={"client_id": cid}).json()
    assert _find_unit(tree2, "HR") is None
    assert _find_unit(tree2, "HR_RECR_ONB") is None


def test_delete_company_protected(client):
    cid, tree = _setup_client(client)
    company = _find_unit(tree, "company")
    assert company

    r = client.delete(f"/api/org-units/{company['id']}?mode=cascade")
    assert r.status_code == 403


def test_clone_global_template_department(client):
    rows = client.get(
        "/api/template-org-units", params={"template_code": "default", "limit": 200}
    ).json()["items"]
    hr = next(r for r in rows if r["code"] == "HR" and r["unit_type"] == "department")

    r = client.post(f"/api/template-org-units/{hr['id']}/clone")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["row"]["code"].startswith("HR_COPY")
    assert "Копия" in data["row"]["name"]
    assert data["position_links_created"] >= 0

    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import PositionDeptType

    db = SessionLocal()
    try:
        copied = db.scalars(
            select(PositionDeptType).where(
                PositionDeptType.template_code == "default",
                PositionDeptType.dept_type_code == data["row"]["code"],
            )
        ).all()
        orig = db.scalars(
            select(PositionDeptType).where(
                PositionDeptType.template_code == "default",
                PositionDeptType.dept_type_code == "HR",
            )
        ).all()
        assert len(copied) == len(orig)
    finally:
        db.close()


def test_global_cascade_delete_template_department(client):
    rows = client.get(
        "/api/template-org-units", params={"template_code": "default", "limit": 200}
    ).json()["items"]
    hr = next(r for r in rows if r["code"] == "HR" and r["unit_type"] == "department")

    clone_r = client.post(f"/api/template-org-units/{hr['id']}/clone")
    assert clone_r.status_code == 201
    clone_id = clone_r.json()["row"]["id"]
    clone_code = clone_r.json()["row"]["code"]

    r = client.delete(f"/api/template-org-units/{clone_id}?mode=cascade")
    assert r.status_code == 204, r.text

    rows2 = client.get(
        "/api/template-org-units", params={"template_code": "default", "limit": 200}
    ).json()["items"]
    assert not any(x["code"] == clone_code for x in rows2)
