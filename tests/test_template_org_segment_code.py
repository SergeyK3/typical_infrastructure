r"""segment_code в типовой оргструктуре — только для department; секции наследуют."""

from __future__ import annotations


def test_segment_code_for_department_only(client):
    tpl = "default"
    dept = client.post(
        "/api/template-org-units",
        json={
            "template_code": tpl,
            "code": "SEG_TEST_DEPT",
            "name": "Отдел с segment",
            "parent_code": "company",
            "unit_type": "department",
            "segment_code": "CLINIC",
        },
    )
    assert dept.status_code == 201, dept.text
    assert dept.json()["segment_code"] == "CLINIC"
    assert dept.json()["effective_segment_code"] == "CLINIC"

    section = client.post(
        "/api/template-org-units",
        json={
            "template_code": tpl,
            "code": "SEG_TEST_SEC",
            "name": "Секция без segment",
            "parent_code": "SEG_TEST_DEPT",
            "unit_type": "section",
        },
    )
    assert section.status_code == 201, section.text
    assert section.json()["segment_code"] is None
    assert section.json()["effective_segment_code"] == "CLINIC"

    bad = client.post(
        "/api/template-org-units",
        json={
            "template_code": tpl,
            "code": "SEG_TEST_BAD",
            "name": "Секция с segment",
            "parent_code": "SEG_TEST_DEPT",
            "unit_type": "section",
            "segment_code": "CLINIC",
        },
    )
    assert bad.status_code == 400


def test_template_segment_codes_list(client):
    listed = client.get("/api/template-segment-codes?template_code=hosp")
    assert listed.status_code == 200
    codes = {x["code"] for x in listed.json()["items"]}
    assert "CLINIC" in codes
    assert "PARACLINIC" in codes
    assert "ADMINISTRATIVE" in codes
