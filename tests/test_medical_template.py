"""Medical enterprise template — wizard dropdown and onboarding deploy."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import OrgUnit, Position, TemplateOrgUnitRow
from app.org_unit_ops import format_org_unit_name
from app.seed import POSITION_CATALOG_SEEDS, _template_org_unit_row, seed_medical_template_bundle


def test_enterprise_templates_include_default_and_medical(client):
    rows = client.get("/api/enterprise-templates").json()
    by_code = {r["code"]: r for r in rows if r.get("is_active", True)}
    assert "default" in by_code
    assert "medical" in by_code
    assert by_code["default"]["name"] == "Общая инфраструктура"
    assert by_code["medical"]["name"] == "Медицинская организация"


def test_seed_medical_template_bundle_backfills_legacy_oper_name(client):
    db = SessionLocal()
    try:
        row = db.scalars(
            select(TemplateOrgUnitRow).where(
                TemplateOrgUnitRow.template_code == "medical",
                TemplateOrgUnitRow.code == "OPER",
            )
        ).first()
        if row is None:
            db.add(
                _template_org_unit_row(
                    "medical",
                    {
                        "code": "OPER",
                        "name": "Медицинский блок",
                        "unit_type": "department",
                        "parent_code": "company",
                        "sort_order": 20,
                        "segment_code": "CLINIC",
                    },
                )
            )
        else:
            row.name = format_org_unit_name("Медицинский блок", "department")
        db.commit()

        seed_medical_template_bundle(db)

        row = db.scalars(
            select(TemplateOrgUnitRow).where(
                TemplateOrgUnitRow.template_code == "medical",
                TemplateOrgUnitRow.code == "OPER",
            )
        ).first()
        assert row is not None
        assert row.name == format_org_unit_name("Операционный блок", "department")
    finally:
        db.close()


def test_medical_structure_preview_is_superset_of_default(client):
    default_preview = client.get("/api/enterprise-templates/default/structure-preview").json()
    medical_preview = client.get("/api/enterprise-templates/medical/structure-preview").json()
    default_codes = {u["code"] for u in default_preview["org_units"]}
    medical_codes = {u["code"] for u in medical_preview["org_units"]}
    assert len(medical_codes) > len(default_codes)
    assert default_codes.issubset(medical_codes)
    for code in ("HR", "ACC", "QUAL"):
        assert code in medical_codes
    for code in ("POLYCLINNC", "STAT", "FACILITY", "ECON", "OPER"):
        assert code in medical_codes
    oper = next(u for u in medical_preview["org_units"] if u["code"] == "OPER")
    assert "операционн" in oper["name"].lower()
    assert "медицинск" not in oper["name"].lower()


def test_medical_positions_include_default_and_medical_roles(client):
    preview = client.get("/api/enterprise-templates/medical/structure-preview").json()
    pos_codes = {p["code"] for p in preview["positions"]}
    default_codes = {p["position_code"] for p in POSITION_CATALOG_SEEDS}
    assert default_codes.issubset(pos_codes)
    for code in ("HR_GENERALIST", "ACC_ACCOUNTANT", "MAIN_NURSE", "ADM_ZAM_STRATEG", "MEDREGISTR"):
        assert code in pos_codes


def test_medical_onboarding_deploys_merged_org_structure(client):
    payload = {
        "template_code": "medical",
        "client": {"code": "med_onboard_x2", "name": "Medical Onboard Test"},
        "admin": {
            "last_name": "Med",
            "first_name": "Admin",
            "login": "med_onboard_admin2",
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
        assert "HR" in ou_codes
        assert "POLYCLINNC" in ou_codes
        assert "STAT" in ou_codes
        assert "FACILITY" in ou_codes

        nurse = db.scalars(
            select(Position).where(
                Position.client_id == client_id,
                Position.position_catalog_code == "MAIN_NURSE",
            )
        ).first()
        assert nurse is not None
    finally:
        db.close()


def test_legacy_hosp_template_code_alias_onboarding(client):
    payload = {
        "template_code": "hosp",
        "client": {"code": "hosp_alias_x2", "name": "Hosp Alias Test"},
        "admin": {
            "last_name": "H",
            "first_name": "A",
            "login": "hosp_alias_admin2",
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
        assert "HR" in ou_codes
    finally:
        db.close()


def test_wizard_dry_run_allows_create_after_success(client):
    html = Path("static/wizard/index.html").read_text(encoding="utf-8")
    assert "runSubmitted = false" in html
    assert "btnCreateAfterDryRun" in html
    assert "run.status === 'dry_run'" in html


def test_wizard_step2_create_mode_hint(client):
    html = Path("static/wizard/index.html").read_text(encoding="utf-8")
    assert "Вы создаёте" in html and "новую организацию" in html
    assert "mode-choice-alt" in html
    assert "Альтернатива:" in html
