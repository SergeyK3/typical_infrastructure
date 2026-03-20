r"""Копии справочников на стороне организации: регламенты, должности из каталога, узел шаблона."""

from __future__ import annotations


def test_copy_global_regulation_to_client(client):
    r = client.post("/api/onboarding-runs", json=_onboarding_body("cc_reg", "cc_reg@t.test"))
    assert r.status_code in (200, 201), r.text
    run = r.json()
    cid = run["client_id"]
    assert cid

    r2 = client.post(
        "/api/client-regulations/copy-from-global",
        json={"client_id": cid, "global_regulation_code": "REG_HR_RECRUITER_V1"},
    )
    assert r2.status_code == 201, r2.text
    detail = r2.json()
    assert detail["regulation_code"] == "REG_HR_RECRUITER_V1"
    assert detail["global_regulation_code"] == "REG_HR_RECRUITER_V1"
    assert detail["client_id"] == cid
    assert len(detail["kpis"]) >= 1

    r3 = client.get("/api/client-regulations", params={"client_id": cid})
    assert r3.status_code == 200
    env = r3.json()
    assert env["total"] == 1


def test_position_from_catalog(client):
    r = client.post("/api/onboarding-runs", json=_onboarding_body("cc_pos", "cc_pos@t.test"))
    assert r.status_code in (200, 201), r.text
    cid = r.json()["client_id"]
    tree = client.get("/api/org-units/tree", params={"client_id": cid}).json()
    hr_id = _find_unit_id(tree, "HR")
    assert hr_id

    cat = client.get("/api/position-catalog", params={"limit": 1}).json()["items"][0]
    pc = cat["position_code"]

    r2 = client.post(
        "/api/positions/from-catalog",
        json={
            "client_id": cid,
            "org_unit_id": hr_id,
            "position_catalog_code": pc,
        },
    )
    assert r2.status_code == 201, r2.text
    pos = r2.json()
    assert pos["position_catalog_code"] == pc
    assert pos["is_detached"] is True


def test_org_unit_from_template_node_empty_client(client):
    r = client.post(
        "/api/clients",
        json={"code": "empty_tpl", "name": "Empty tpl", "status": "active"},
    )
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    r2 = client.post(
        "/api/org-units/from-template-node",
        json={"client_id": cid, "template_unit_code": "company", "template_code": "default"},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["code"] == "company"

    r3 = client.post(
        "/api/org-units/from-template-node",
        json={"client_id": cid, "template_unit_code": "HR", "template_code": "default"},
    )
    assert r3.status_code == 201, r3.text
    assert r3.json()["code"] == "HR"


def _onboarding_body(code: str, login: str) -> dict:
    return {
        "template_code": "default",
        "client": {"code": code, "name": code},
        "admin": {
            "last_name": "A",
            "first_name": "B",
            "login": login,
            "password": "TempPass123!",
            "email": login,
        },
    }


def _find_unit_id(nodes, code: str):
    for n in nodes:
        if n.get("code") == code:
            return n["id"]
        found = _find_unit_id(n.get("children") or [], code)
        if found:
            return found
    return None
