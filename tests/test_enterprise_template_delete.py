r"""DELETE /api/enterprise-templates — полное удаление архивного bundle."""

from __future__ import annotations


def _clone_archived(client, code: str):
    rows = client.get("/api/enterprise-templates").json()
    src = next(t for t in rows if t["code"] == "default")
    r = client.post(
        f"/api/enterprise-templates/{src['id']}/clone",
        json={"new_code": code, "new_name": code, "copy_positions": True},
    )
    assert r.status_code == 201, r.text
    tid = r.json()["template"]["id"]
    ar = client.post(f"/api/enterprise-templates/{tid}/archive")
    assert ar.status_code == 200, ar.text
    return tid, code


def test_delete_archived_template_removes_bundle(client):
    tid, code = _clone_archived(client, "del_bundle_test")

    r = client.delete(f"/api/enterprise-templates/{tid}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["deleted"] is True
    assert data["template_code"] == code
    assert data["counts"]["org_units"] >= 1

    assert client.get(f"/api/enterprise-templates/{tid}").status_code == 404
    cat = client.get("/api/position-catalog", params={"template_code": code}).json()
    assert cat["total"] == 0


def test_delete_non_archived_rejected(client):
    rows = client.get("/api/enterprise-templates").json()
    src = next(t for t in rows if t["code"] == "default")
    r = client.post(
        f"/api/enterprise-templates/{src['id']}/clone",
        json={"new_code": "del_draft_test", "new_name": "draft"},
    )
    assert r.status_code == 201
    tid = r.json()["template"]["id"]
    r2 = client.delete(f"/api/enterprise-templates/{tid}")
    assert r2.status_code == 409


def test_delete_default_forbidden(client):
    rows = client.get("/api/enterprise-templates").json()
    default = next(t for t in rows if t["code"] == "default")
    client.post(f"/api/enterprise-templates/{default['id']}/archive")
    r = client.delete(f"/api/enterprise-templates/{default['id']}")
    assert r.status_code == 403
    client.post(f"/api/enterprise-templates/{default['id']}/restore")
