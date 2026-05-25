r"""PATCH /api/enterprise-templates — переименование и свойства шаблона."""

from __future__ import annotations


def _default_template(client):
    rows = client.get("/api/enterprise-templates").json()
    assert rows, "expected at least one enterprise template"
    tpl = next((t for t in rows if t["code"] == "default"), rows[0])
    return tpl


def test_patch_template_name(client):
    tpl = _default_template(client)
    new_name = tpl["name"] + " (test)"
    r = client.patch(
        f"/api/enterprise-templates/{tpl['id']}",
        json={"name": new_name},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == new_name

    r2 = client.get(f"/api/enterprise-templates/{tpl['id']}")
    assert r2.status_code == 200
    assert r2.json()["name"] == new_name

    client.patch(
        f"/api/enterprise-templates/{tpl['id']}",
        json={"name": tpl["name"]},
    )


def test_patch_archived_template_rejected(client):
    tpl = _default_template(client)
    clone = client.post(
        f"/api/enterprise-templates/{tpl['id']}/clone",
        json={"new_code": "patch_arch_test", "new_name": "Patch arch test"},
    )
    assert clone.status_code == 201, clone.text
    cloned_id = clone.json()["template"]["id"]

    ar = client.post(f"/api/enterprise-templates/{cloned_id}/archive")
    assert ar.status_code == 200, ar.text

    r = client.patch(
        f"/api/enterprise-templates/{cloned_id}",
        json={"name": "Should fail"},
    )
    assert r.status_code == 409, r.text
    detail = r.json()
    code = detail.get("detail") or detail.get("error", {}).get("code")
    assert code in ("template_archived", {"code": "template_archived"})
