r"""Переименование кода узла типовой оргструктуры."""

from __future__ import annotations


def _default_template(client):
    rows = client.get("/api/enterprise-templates").json()
    return next(t for t in rows if t["code"] == "default")


def test_rename_template_org_unit_code(client):
    tpl = _default_template(client)
    template_code = tpl["code"]

    created = client.post(
        "/api/template-org-units",
        json={
            "template_code": template_code,
            "code": "REN_OLD",
            "name": "До переименования",
            "parent_code": "company",
            "unit_type": "department",
            "sort_order": 88,
        },
    )
    assert created.status_code == 201, created.text
    row_id = created.json()["id"]

    section = client.post(
        "/api/template-org-units",
        json={
            "template_code": template_code,
            "code": "REN_SEC",
            "name": "Секция",
            "parent_code": "REN_OLD",
            "unit_type": "section",
            "sort_order": 1,
        },
    )
    assert section.status_code == 201, section.text

    patched = client.patch(
        f"/api/template-org-units/{row_id}",
        json={"code": "REN_NEW", "name": "После переименования"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["code"] == "REN_NEW"

    tree = client.get(
        "/api/template-org-units/tree", params={"template_code": template_code}
    ).json()

    def find(nodes, code):
        for n in nodes:
            if n["code"] == code:
                return n
            found = find(n.get("children") or [], code)
            if found:
                return found
        return None

    dept = find(tree, "REN_NEW")
    assert dept is not None
    sec = find(tree, "REN_SEC")
    assert sec is not None
    assert sec["parent_code"] == "REN_NEW"

    client.delete(f"/api/template-org-units/{section.json()['id']}")
    client.delete(f"/api/template-org-units/{row_id}")
