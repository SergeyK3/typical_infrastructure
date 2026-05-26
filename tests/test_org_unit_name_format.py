"""Tests for org unit name formatting rules."""

from __future__ import annotations

from app.org_unit_ops import format_org_unit_name
from app.org_structures import get_template_structure


def test_department_name_uppercase():
    assert format_org_unit_name("Отдел продаж", "department") == "ОТДЕЛ ПРОДАЖ"
    assert format_org_unit_name("hr", "department") == "HR"


def test_section_name_sentence_case():
    assert format_org_unit_name("Найм и введение", "section") == "Найм и введение"
    assert format_org_unit_name("НАЙМ И ВВЕДЕНИЕ", "section") == "Найм и введение"
    assert format_org_unit_name("Связь со СМИ", "section") == "Связь со сми"


def test_company_name_unchanged():
    assert format_org_unit_name("Компания", "company") == "Компания"


def test_default_template_structure_uses_formatting():
    units = {u["code"]: u for u in get_template_structure("default")}
    assert units["HR"]["name"] == "HR"
    assert units["SALES"]["name"] == "ОТДЕЛ ПРОДАЖ"
    assert units["HR_RECR_ONB"]["name"] == "Найм и введение"


def test_onboarding_creates_formatted_org_names(client):
    payload = {
        "template_code": "default",
        "client": {"code": "org_name_fmt_x", "name": "Org Name Fmt"},
        "admin": {
            "last_name": "A",
            "first_name": "B",
            "login": "org_name_fmt_admin",
            "password": "X",
            "email": None,
        },
    }
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    client_id = r.json()["client_id"]
    items = client.get(f"/api/org-units?client_id={client_id}&limit=500").json()["items"]
    by_code = {u["code"]: u for u in items}
    assert by_code["SALES"]["name"] == "ОТДЕЛ ПРОДАЖ"
    assert by_code["HR_RECR_ONB"]["name"] == "Найм и введение"
