"""Medical enterprise template — wizard dropdown and onboarding deploy."""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import OrgUnit, Position


def test_enterprise_templates_include_default_and_medical(client):
    rows = client.get("/api/enterprise-templates").json()
    by_code = {r["code"]: r for r in rows if r.get("is_active", True)}
    assert "default" in by_code
    assert "medical" in by_code
    assert by_code["default"]["name"] == "Общая инфраструктура"
    assert by_code["medical"]["name"] == "Медицинская организация"


def test_medical_structure_preview_has_clinical_departments(client):
    preview = client.get("/api/enterprise-templates/medical/structure-preview").json()
    codes = {u["code"] for u in preview["org_units"]}
    assert "POLYCLINNC" in codes
    assert "STAT" in codes
    pos_codes = {p["code"] for p in preview["positions"]}
    assert "MAIN_NURSE" in pos_codes
    assert "ORDINATOR amb" in pos_codes


def test_medical_onboarding_deploys_medical_org_structure(client):
    payload = {
        "template_code": "medical",
        "client": {"code": "med_onboard_x", "name": "Medical Onboard Test"},
        "admin": {
            "last_name": "Med",
            "first_name": "Admin",
            "login": "med_onboard_admin",
            "password": "MedPass123!",
            "email": None,
        },
    }
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text
    client_id = r.json()["client_id"]

    db = SessionLocal()
    try:
        ou_codes = {
            row.code
            for row in db.scalars(
                select(OrgUnit).where(OrgUnit.client_id == client_id)
            ).all()
        }
        assert "POLYCLINNC" in ou_codes
        assert "STAT" in ou_codes
        assert "ADMISSION" in ou_codes

        nurse = db.scalars(
            select(Position).where(
                Position.client_id == client_id,
                Position.position_catalog_code == "MAIN_NURSE",
            )
        ).first()
        assert nurse is not None
        ou = db.get(OrgUnit, nurse.org_unit_id)
        assert ou is not None
        assert ou.code == "ADM"
    finally:
        db.close()


def test_legacy_hosp_template_code_alias_onboarding(client):
    payload = {
        "template_code": "hosp",
        "client": {"code": "hosp_alias_x", "name": "Hosp Alias Test"},
        "admin": {
            "last_name": "H",
            "first_name": "A",
            "login": "hosp_alias_admin",
            "password": "HospPass123!",
            "email": None,
        },
    }
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text
    client_id = r.json()["client_id"]

    db = SessionLocal()
    try:
        ou_codes = {
            row.code
            for row in db.scalars(
                select(OrgUnit).where(OrgUnit.client_id == client_id)
            ).all()
        }
        assert "STAT" in ou_codes
    finally:
        db.close()
