r"""log_group в типовой оргструктуре — для отделений и секций."""

from __future__ import annotations


def _default_template(client):
    rows = client.get("/api/enterprise-templates").json()
    return next(t for t in rows if t["code"] == "default")


def test_log_group_for_department_and_section(client):
    tpl = _default_template(client)
    template_code = tpl["code"]

    dept = client.post(
        "/api/template-org-units",
        json={
            "template_code": template_code,
            "code": "LG_TEST_DEPT",
            "name": "Отдел с log_group",
            "parent_code": "company",
            "unit_type": "department",
            "log_group": "hr_ops",
            "sort_order": 99,
        },
    )
    assert dept.status_code == 201, dept.text
    assert dept.json()["log_group"] == "hr_ops"

    section = client.post(
        "/api/template-org-units",
        json={
            "template_code": template_code,
            "code": "LG_TEST_SEC",
            "name": "Секция с log_group",
            "parent_code": "LG_TEST_DEPT",
            "unit_type": "section",
            "log_group": "hr_intake",
            "sort_order": 1,
        },
    )
    assert section.status_code == 201, section.text
    assert section.json()["log_group"] == "hr_intake"

    bad = client.post(
        "/api/template-org-units",
        json={
            "template_code": template_code,
            "code": "LG_TEST_CO",
            "name": "Компания с log_group",
            "parent_code": None,
            "unit_type": "company",
            "log_group": "forbidden",
            "sort_order": 0,
        },
    )
    assert bad.status_code in (400, 422), bad.text

    dept_id = dept.json()["id"]
    patch_name = client.patch(
        f"/api/template-org-units/{dept_id}",
        json={"name": "Отдел переименован"},
    )
    assert patch_name.status_code == 200, patch_name.text
    assert patch_name.json()["log_group"] == "hr_ops"

    patch = client.patch(
        f"/api/template-org-units/{dept_id}",
        json={"unit_type": "section"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["log_group"] == "hr_ops"

    client.delete(f"/api/template-org-units/{section.json()['id']}")
    client.delete(f"/api/template-org-units/{dept_id}")
